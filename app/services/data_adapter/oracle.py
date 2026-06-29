from typing import Any, Dict, List, Optional, Tuple, Set, Union
import asyncio
from .base import DataSourceAdapter
from .models import LogicalQuery, ResultSet
from app.schemas.resource import ResourceResponse
import logging
import inspect
try:
    import oracledb
except ImportError:
    oracledb = None

import re
from jinja2 import Environment, BaseLoader, meta, StrictUndefined
from app.utils.jinja_sql import SQL_LAB_ENV
from .base import SQLSafetyError

logger = logging.getLogger(__name__)

TEMPLATE_ENV = Environment(loader=BaseLoader(), undefined=StrictUndefined)
SQL_LAB_ENV = SQL_LAB_ENV

class OracleAdapter(DataSourceAdapter):
    """Oracle Adapter supporting both Thin (Async) and Thick (Sync) modes with Oracle 11g compatibility"""
    
    def __init__(self, source_id: int):
        self.source_id = source_id

    async def _run_query_internal(self, sql: str, params: Dict[str, Any] = None, fetch_all: bool = True) -> Tuple[List[Any], Any]:
        """
        Internal helper to run any SQL on Oracle, automatically handling Sync (Thick) vs Async (Thin) pools.
        Returns (rows, description).
        """
        from app.services.pool_manager import DataSourcePoolManager
        pool = await DataSourcePoolManager.get_pool(self.source_id)
        params = params or {}
        
        # Determine if pool is async (Thin) or sync (Thick)
        # In oracledb, AsyncPool has acquire() as a coroutine.
        is_async = hasattr(pool, 'acquire') and inspect.iscoroutinefunction(pool.acquire)

        if is_async:
            # --- Thin Mode (Async) ---
            conn = await pool.acquire()
            async with conn:
                async with conn.cursor() as cursor:
                    logger.debug(f"Oracle [Thin/Async] executing: {sql[:200]}...")
                    await cursor.execute(sql, params)
                    rows = await cursor.fetchall() if fetch_all else []
                    return rows, cursor.description
        else:
            # --- Thick Mode (Sync) ---
            def sync_execute():
                with pool.acquire() as conn:
                    with conn.cursor() as cursor:
                        logger.debug(f"Oracle [Thick/Sync] executing: {sql[:200]}...")
                        cursor.execute(sql, params)
                        rows = cursor.fetchall() if fetch_all else []
                        # Convert description to a portable list since cursor object might be closed
                        desc = [list(d) for d in cursor.description] if cursor.description else None
                        return rows, desc

            # Use to_thread to keep the event loop responsive
            return await asyncio.to_thread(sync_execute)

    def _get_pagination_sql(self, sql: str, offset: int, limit: int) -> str:
        """
        Generate Oracle 11g compatible pagination SQL using ROWNUM.
        Oracle 12c 'FETCH FIRST' is not supported in 11g.
        """
        clean_sql = sql.strip().rstrip(";")
        
        # Standard Oracle 11g Pagination Pattern (Double Wrap)
        # This handles ORDER BY correctly by wrapping it in a subquery first.
        return f"""
            SELECT * FROM (
                SELECT "_sub".*, ROWNUM AS "_rn"
                FROM (
                    {clean_sql}
                ) "_sub"
                WHERE ROWNUM <= {offset + limit}
            )
            WHERE "_rn" > {offset}
        """

    def _render_sql(self, config: ResourceResponse, query: LogicalQuery) -> Tuple[str, Set[str], Dict[str, Any]]:
        if config.resource_mode != "SQL" or not config.custom_sql:
            return config.custom_sql or "", set(), {}

        ctx = {f: v for f, op, v in query.filters}
        if "{%" not in config.custom_sql and "{{" not in config.custom_sql:
            return config.custom_sql, set(), {}

        try:
            env = TEMPLATE_ENV
            template = env.from_string(config.custom_sql)
            rendered = template.render(**ctx)
            ast = env.parse(config.custom_sql)
            undeclared = meta.find_undeclared_variables(ast)
            
            template_params = {var: ctx[var] for var in undeclared if var in ctx}
            return rendered, undeclared, template_params
        except Exception as e:
            logger.error(f"Oracle Template rendering failed: {e}")
            raise ValueError(f"SQL Template Error: {e}")

    def _get_source_sql(self, config: ResourceResponse, rendered_sql: Optional[str] = None) -> str:
        if config.resource_mode == "SQL":
            sql = rendered_sql if rendered_sql is not None else config.custom_sql
            return f"({sql.strip().rstrip(';')}) \"_sub\""
        return f"\"{config.table_name}\""

    def _build_where(self, query: LogicalQuery, config: ResourceResponse, exclude: Set[str] = None) -> Tuple[str, Dict[str, Any]]:
        allowed = [f.name for f in config.allowed_filters]
        where_parts, params = [], {}
        exclude = exclude or set()
        
        for i, (f, op, v) in enumerate(query.filters):
            if f not in allowed or f in exclude: continue
            p_name = f"{f}_{i}"
            col = f"\"{f}\""
            if op == "=":
                where_parts.append(f"{col} = :{p_name}"); params[p_name] = v
            elif op == "IN":
                if isinstance(v, (list, tuple)):
                    placeholders = []
                    for j, item in enumerate(v):
                        p_sub = f"{p_name}_{j}"; placeholders.append(f":{p_sub}"); params[p_sub] = item
                    where_parts.append(f"{col} IN ({', '.join(placeholders)})")
                else:
                    where_parts.append(f"{col} = :{p_name}"); params[p_name] = v
            elif op in (">", "<", ">=", "<=", "!="):
                where_parts.append(f"{col} {op} :{p_name}"); params[p_name] = v
            elif op.upper() == "LIKE":
                where_parts.append(f"{col} LIKE :{p_name}"); params[p_name] = v
            
        return (" AND ".join(where_parts) if where_parts else "1=1"), params

    async def execute(self, query: LogicalQuery) -> ResultSet:
        from app.services.meta_service import MetaService
        config = await MetaService.get_config(query.resource)
        if not config: raise ValueError(f"Unknown resource: {query.resource}")

        fields = [f.name for f in config.fields_config]
        rendered_sql, used_vars, t_params = self._render_sql(config, query)
        source = self._get_source_sql(config, rendered_sql)
        where_sql, auto_params = self._build_where(query, config, exclude=used_vars)
        final_params = {**auto_params, **t_params}

        # 1. Total Count
        count_sql = f"SELECT COUNT(*) FROM {source} WHERE {where_sql}"
        rows, _ = await self._run_query_internal(count_sql, final_params)
        total = rows[0][0] if rows else 0

        # 2. Data Fetch (11g compatible)
        sort_field = query.sort_by if (query.sort_by and any(f.name == query.sort_by for f in config.allowed_filters)) else config.default_sort
        if not sort_field and fields: sort_field = fields[0]
        sort_order = "DESC" if query.sort_order.upper() == "DESC" else "ASC"
        offset = (query.page - 1) * query.size
        
        quoted_fields = [f'"{f}"' for f in fields]
        fields_str = ", ".join(quoted_fields)
        base_sql = f"SELECT {fields_str} FROM {source} WHERE {where_sql}"
        if sort_field:
            base_sql += f" ORDER BY \"{sort_field}\" {sort_order}"
            
        data_sql = self._get_pagination_sql(base_sql, offset, query.size)
        rows, _ = await self._run_query_internal(data_sql, final_params)

        items = []
        for row in rows:
            items.append({field: (str(row[i]) if row[i] is not None else None) for i, field in enumerate(fields)})

        return ResultSet(items=items, total=total, page=query.page, size=query.size, pages=(total + query.size - 1) // query.size, generated_sql=data_sql.strip())

    async def execute_summary(self, query: LogicalQuery) -> Dict[str, Any]:
        return {}

    async def execute_sql(self, sql: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        rows, description = await self._run_query_internal(sql, params)
        columns = [{"name": desc[0], "type": str(desc[1])} for desc in description] if description else []
        return {"columns": columns, "items": [list(row) for row in rows]}

    async def get_tables(self) -> List[Dict[str, str]]:
        # Combined Tables and Views for Oracle
        sql = """
            SELECT table_name, 'TABLE' as type FROM user_tables 
            UNION ALL 
            SELECT view_name as table_name, 'VIEW' as type FROM user_views 
            ORDER BY type, table_name
        """
        rows, _ = await self._run_query_internal(sql)
        return [{"name": row[0], "type": row[1]} for row in rows]

    async def get_columns(self, table_name: Optional[str] = None, custom_sql: Optional[str] = None, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, str]]:
        if custom_sql:
            raw_sql = custom_sql.strip().rstrip(";")
            try:
                env = SQL_LAB_ENV
                sql = env.from_string(raw_sql).render(**(params or {}))
            except: sql = raw_sql
            final_sql = f"SELECT * FROM ({sql}) \"t\" WHERE ROWNUM <= 0"
            _, description = await self._run_query_internal(final_sql)
            return [{"name": desc[0], "type": str(desc[1]), "comment": ""} for desc in (description or [])]
        else:
            # Oracle 11g standard metadata query
            sql = """
                SELECT c.column_name, c.data_type, cm.comments
                FROM user_tab_columns c
                LEFT JOIN user_col_comments cm ON c.table_name = cm.table_name AND c.column_name = cm.column_name
                WHERE c.table_name = :t
                ORDER BY c.column_id
            """
            rows, _ = await self._run_query_internal(sql, {"t": table_name.upper() if table_name else ""})
            return [{"name": row[0], "type": row[1], "comment": row[2] or ""} for row in rows]

    async def preview(self, sql: str, limit: int = 100, params: Dict[str, Any] = None) -> Dict[str, Any]:
        import time
        params = params or {}
        self._validate_sql_safety(sql)
        
        # 1. Jinja2 Rendering
        rendered_sql = sql
        if "{{" in sql or "{%" in sql:
            try:
                # Use DebugUndefined to keep variables if they are not in params (for manual :var binding)
                rendered_sql = SQL_LAB_ENV.from_string(sql).render(**params)
                self._validate_sql_safety(rendered_sql)
            except Exception as e: raise ValueError(f"Template rendering failed: {e}")

        # 2. Pagination Wrapping (Oracle 11g compatible)
        clean_sql = rendered_sql.strip().rstrip(";")
        sql_upper = clean_sql.upper()
        
        if "ROWNUM" in sql_upper or "FETCH FIRST" in sql_upper:
            final_sql = clean_sql
        else:
            # Handle CTE (WITH ... SELECT)
            if sql_upper.startswith("WITH"):
                # Pattern: WITH ... SELECT ... -> WITH ... SELECT * FROM (SELECT ...) WHERE ROWNUM <= limit
                # Find the last SELECT (very basic heuristic)
                select_match = list(re.finditer(r"\bSELECT\b", sql_upper))
                if select_match:
                    last_select_pos = select_match[-1].start()
                    with_part = clean_sql[:last_select_pos]
                    select_part = clean_sql[last_select_pos:]
                    final_sql = f"{with_part} SELECT * FROM ({select_part}) WHERE ROWNUM <= {limit}"
                else:
                    final_sql = f"SELECT * FROM ({clean_sql}) WHERE ROWNUM <= {limit}"
            else:
                final_sql = f"SELECT * FROM ({clean_sql}) WHERE ROWNUM <= {limit}"
        
        start_time = time.perf_counter()
        
        # 3. Parameter Handling (Oracle 11g compatibility fix)
        # Only pass params to cursor.execute if the rendered SQL actually contains ':' placeholders.
        # Otherwise, passing full params dict to oracledb often leads to ORA-01036.
        execute_params = params if ":" in final_sql else {}
        
        rows, description = await self._run_query_internal(final_sql, execute_params)
        columns = [{"name": desc[0], "type": str(desc[1])} for desc in description] if description else []
        
        return {
            "columns": columns,
            "rows": [list(row) for row in rows],
            "execution_time_ms": (time.perf_counter() - start_time) * 1000,
            "scanned_rows": 0
        }
