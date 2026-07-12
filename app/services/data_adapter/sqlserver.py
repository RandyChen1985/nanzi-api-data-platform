"""SQL Server 数据源适配器（aioodbc / T-SQL）。"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional, Set, Tuple

from jinja2 import meta

from app.schemas.resource import ResourceResponse
from app.utils.jinja_sql import SQL_LAB_ENV, TEMPLATE_ENV
from .base import DataSourceAdapter, SQLSafetyError
from .models import LogicalQuery, ResultSet

logger = logging.getLogger(__name__)


class SqlServerAdapter(DataSourceAdapter):
    """SQL Server Adapter — 参数占位符 ``?``，标识符 ``[name]``。"""

    def __init__(self, source_id: int):
        self.source_id = source_id

    def _quote(self, name: str) -> str:
        return f"[{name.replace(']', ']]')}]"

    def _clean_value(self, field: str, value: Any) -> Any:
        return value

    def _render_sql(self, config: ResourceResponse, query: LogicalQuery) -> Tuple[str, Set[str], List[Any]]:
        if config.resource_mode != "SQL" or not config.custom_sql:
            return config.custom_sql or "", set(), []

        ctx: Dict[str, Any] = {}
        for f, _op, v in query.filters:
            if f not in ctx:
                ctx[f] = v

        if "{% " not in config.custom_sql and "{{" not in config.custom_sql:
            return config.custom_sql, set(), []

        env = TEMPLATE_ENV
        try:
            ast = env.parse(config.custom_sql)
            undeclared = meta.find_undeclared_variables(ast)
            template = env.from_string(config.custom_sql)
            rendered = template.render(**ctx)

            template_params_list: List[Any] = []

            def replace_placeholder(match: re.Match) -> str:
                var_name = match.group(1)
                if var_name in ctx:
                    template_params_list.append(self._clean_value(var_name, ctx[var_name]))
                    return "?"
                raise ValueError(f"Missing required parameter: {var_name}")

            rendered = re.sub(r"\{\{\s*(\w+)\s*\}\}", replace_placeholder, rendered)
            return rendered, undeclared, template_params_list
        except Exception as exc:
            logger.error("Template rendering failed: %s", exc)
            raise ValueError(f"SQL Template Error: {exc}. SQL: {config.custom_sql}") from exc

    def _get_source_sql(self, config: ResourceResponse, rendered_sql: Optional[str] = None) -> str:
        if config.resource_mode == "TABLE":
            return self._quote(config.table_name or "")
        sql = rendered_sql if rendered_sql else config.custom_sql
        return f"({sql}) AS subquery"

    def _build_where(
        self,
        query: LogicalQuery,
        config: ResourceResponse,
        exclude: Optional[Set[str]] = None,
    ) -> tuple[str, tuple]:
        allowed = [f.name for f in config.allowed_filters]
        where_parts: List[str] = []
        params: List[Any] = []
        exclude = exclude or set()

        for f, op, v in query.filters:
            if f not in allowed or f in exclude:
                continue
            col = self._quote(f)
            if op == "=":
                where_parts.append(f"{col} = ?")
                params.append(v)
            elif op == "IN":
                if isinstance(v, (list, tuple)) and v:
                    placeholders = ", ".join(["?"] * len(v))
                    where_parts.append(f"{col} IN ({placeholders})")
                    params.extend(v)
            elif op in (">", "<", ">=", "<=", "!="):
                where_parts.append(f"{col} {op} ?")
                params.append(v)
            else:
                logger.warning("Unsupported operator: %s", op)

        where_sql = " AND ".join(where_parts) if where_parts else "1=1"
        return where_sql, tuple(params)

    async def execute(self, query: LogicalQuery) -> ResultSet:
        from app.services.meta_service import MetaService
        from app.services.pool_manager import DataSourcePoolManager

        config = await MetaService.get_config(query.resource)
        if not config:
            raise ValueError(f"Unknown resource: {query.resource}")

        pool = await DataSourcePoolManager.get_pool(self.source_id)
        rendered_sql, used_vars, template_params_list = self._render_sql(config, query)
        source = self._get_source_sql(config, rendered_sql)
        where_sql, auto_params_tuple = self._build_where(query, config, exclude=used_vars)

        select_fields = [f.name for f in config.fields_config]
        select_fields_str = ", ".join(self._quote(f) for f in select_fields)

        sort_field = query.sort_by if (query.sort_by and query.sort_by in select_fields) else config.default_sort
        sort_order = "DESC" if query.sort_order.upper() == "DESC" else "ASC"
        offset = (query.page - 1) * query.size

        sql = f"""
            SELECT {select_fields_str}
            FROM {source}
            WHERE {where_sql}
            ORDER BY {self._quote(sort_field)} {sort_order}
            OFFSET ? ROWS FETCH NEXT ? ROWS ONLY
        """
        final_params = tuple(template_params_list) + auto_params_tuple + (offset, query.size)

        async with pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(sql, final_params)
                rows = await cursor.fetchall()
                columns = [d[0] for d in cursor.description] if cursor.description else []

        items = [dict(zip(columns, row)) for row in rows]
        return ResultSet(
            items=items,
            total=len(items),
            page=query.page,
            size=query.size,
            pages=(len(items) + query.size - 1) // query.size if items else 0,
            generated_sql=sql.strip(),
        )

    async def execute_summary(self, query: LogicalQuery, agg_fields: List[str]) -> Dict[str, Any]:
        from app.services.meta_service import MetaService
        from app.services.pool_manager import DataSourcePoolManager

        config = await MetaService.get_config(query.resource)
        if not config:
            raise ValueError(f"Unknown resource: {query.resource}")

        pool = await DataSourcePoolManager.get_pool(self.source_id)
        rendered_sql, used_vars, template_params_list = self._render_sql(config, query)
        source = self._get_source_sql(config, rendered_sql)
        where_sql, auto_params_tuple = self._build_where(query, config, exclude=used_vars)

        agg_exprs = [f"COUNT(DISTINCT {self._quote(field)}) AS {self._quote(field + '_count')}" for field in agg_fields]
        sql = f"""
            SELECT {', '.join(agg_exprs)}
            FROM {source}
            WHERE {where_sql}
        """
        final_params = tuple(template_params_list) + auto_params_tuple

        async with pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(sql, final_params)
                row = await cursor.fetchone()
                columns = [d[0] for d in cursor.description] if cursor.description else []

        return dict(zip(columns, row)) if row and columns else {}

    async def get_tables(self) -> List[Dict[str, str]]:
        from app.services.pool_manager import DataSourcePoolManager

        pool = await DataSourcePoolManager.get_pool(self.source_id)
        sql = """
            SELECT TABLE_NAME, TABLE_TYPE
            FROM INFORMATION_SCHEMA.TABLES
            WHERE TABLE_SCHEMA NOT IN ('sys', 'INFORMATION_SCHEMA')
            ORDER BY TABLE_NAME
        """
        async with pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(sql)
                rows = await cursor.fetchall()

        result: List[Dict[str, str]] = []
        for row in rows:
            name, table_type = row[0], (row[1] or "").upper()
            result.append(
                {
                    "name": name,
                    "type": "VIEW" if "VIEW" in table_type else "TABLE",
                }
            )
        return result

    async def get_columns(
        self,
        table_name: Optional[str] = None,
        custom_sql: Optional[str] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, str]]:
        from app.services.pool_manager import DataSourcePoolManager

        pool = await DataSourcePoolManager.get_pool(self.source_id)

        if custom_sql:
            raw_sql = custom_sql.strip().rstrip(";")
            try:
                template = SQL_LAB_ENV.from_string(raw_sql)
                render_ctx = params if params is not None else {}
                sql = template.render(**render_ctx)
            except Exception as exc:
                logger.warning("Template render failed during get_columns, using raw SQL: %s", exc)
                sql = raw_sql

            final_sql = f"SELECT TOP 0 * FROM ({sql}) AS t"
            async with pool.acquire() as conn:
                async with conn.cursor() as cursor:
                    try:
                        await cursor.execute(final_sql)
                        columns = [desc[0] for desc in cursor.description]
                    except Exception as exc:
                        logger.error("Failed to fetch columns for SQL Server: %s SQL: %s", exc, final_sql)
                        raise ValueError(f"Invalid SQL or Table: {exc}") from exc
            return [{"name": col, "type": "String", "comment": ""} for col in columns]

        if table_name:
            sql = """
                SELECT COLUMN_NAME, DATA_TYPE, ''
                FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_NAME = ?
                ORDER BY ORDINAL_POSITION
            """
            async with pool.acquire() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(sql, (table_name,))
                    rows = await cursor.fetchall()
            return [{"name": row[0], "type": row[1] or "String", "comment": row[2] or ""} for row in rows]

        return []

    async def execute_sql(self, sql: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        from app.services.pool_manager import DataSourcePoolManager

        if params is not None and not params:
            params = None

        pool = await DataSourcePoolManager.get_pool(self.source_id)
        async with pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(sql, params)
                rows = await cursor.fetchall()
                columns = []
                if cursor.description:
                    for desc in cursor.description:
                        columns.append({"name": desc[0], "type": str(desc[1])})
                items = [list(row) for row in rows]
                return {"columns": columns, "items": items}

    async def preview(self, sql: str, limit: int = 100, params: Dict[str, Any] = None, offset: int = 0, include_total: bool = False) -> Dict[str, Any]:
        import time

        params = params or {}
        try:
            self._validate_sql_safety(sql)
        except SQLSafetyError as exc:
            raise ValueError(str(exc)) from exc

        rendered_sql = sql
        if "{{" in sql or "{%" in sql:
            try:
                template = SQL_LAB_ENV.from_string(sql)
                rendered_sql = template.render(**params)
                self._validate_sql_safety(rendered_sql)
            except SQLSafetyError as exc:
                raise ValueError(str(exc)) from exc
            except Exception as exc:
                raise ValueError(f"Template rendering failed: {str(exc)}") from exc

        clean_sql = rendered_sql.strip().rstrip(";")
        upper = clean_sql.upper()
        if "TOP " in upper or "FETCH NEXT" in upper or "OFFSET " in upper:
            final_sql = clean_sql
        elif offset > 0:
            final_sql = (
                f"SELECT * FROM ({clean_sql}) AS _preview_sub "
                f"ORDER BY (SELECT NULL) OFFSET {offset} ROWS FETCH NEXT {limit} ROWS ONLY"
            )
        else:
            final_sql = f"SELECT TOP {limit} * FROM ({clean_sql}) AS _preview_sub"

        start_time = time.perf_counter()
        from app.services.pool_manager import DataSourcePoolManager

        pool = await DataSourcePoolManager.get_pool(self.source_id)
        total_count = None
        async with pool.acquire() as conn:
            async with conn.cursor() as cursor:
                if include_total and "TOP " not in upper and "OFFSET " not in upper:
                    await cursor.execute(f"SELECT COUNT(*) FROM ({clean_sql}) AS _cnt")
                    count_row = await cursor.fetchone()
                    total_count = int(count_row[0]) if count_row else 0

                await cursor.execute(final_sql)
                rows = await cursor.fetchall()
                columns = [{"name": desc[0], "type": str(desc[1])} for desc in cursor.description] if cursor.description else []
                items = [list(row) for row in rows]

        execution_time = (time.perf_counter() - start_time) * 1000
        result = {
            "columns": columns,
            "rows": items,
            "execution_time_ms": execution_time,
            "scanned_rows": 0,
            "offset": offset,
            "limit": limit,
        }
        if total_count is not None:
            result["total_count"] = total_count
        return result

    async def explain(self, sql: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
        import time
        params = params or {}
        try:
            self._validate_sql_safety(sql)
        except SQLSafetyError as exc:
            raise ValueError(str(exc)) from exc

        rendered_sql = sql
        if "{{" in sql or "{%" in sql:
            template = SQL_LAB_ENV.from_string(sql)
            rendered_sql = template.render(**params)
            self._validate_sql_safety(rendered_sql)

        clean_sql = rendered_sql.strip().rstrip(";")
        explain_sql = f"SET SHOWPLAN_ALL ON; {clean_sql}; SET SHOWPLAN_ALL OFF"

        start_time = time.perf_counter()
        from app.services.pool_manager import DataSourcePoolManager
        pool = await DataSourcePoolManager.get_pool(self.source_id)
        async with pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(f"SET SHOWPLAN_ALL ON")
                await cursor.execute(clean_sql)
                rows = await cursor.fetchall()
                columns = [{"name": desc[0], "type": str(desc[1])} for desc in cursor.description] if cursor.description else []
                await cursor.execute("SET SHOWPLAN_ALL OFF")

        return {
            "columns": columns,
            "rows": [list(r) for r in rows],
            "execution_time_ms": (time.perf_counter() - start_time) * 1000,
        }
