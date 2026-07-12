from typing import Any, Dict, List, Optional, Tuple, Set
from .base import DataSourceAdapter
from .models import LogicalQuery, ResultSet
from app.schemas.resource import ResourceResponse
import aiomysql
import logging
from jinja2 import meta
from app.utils.jinja_sql import SQL_LAB_ENV, TEMPLATE_ENV

logger = logging.getLogger(__name__)


class MySQLAdapter(DataSourceAdapter):
    """MySQL Adapter using aiomysql with parameterized queries"""
    
    def __init__(self, source_id: int):
        self.source_id = source_id
    
    def _clean_value(self, field: str, value: Any) -> Any:
        """Helper to sanitize/convert values (e.g. timestamps)"""
        # For MySQL, we can pass most values directly
        # Add specific conversions if needed
        return value
    
    def _render_sql(self, config: ResourceResponse, query: LogicalQuery) -> Tuple[str, Set[str], List[Any]]:
        """
        Render Custom SQL using Jinja2 if applicable.
        Returns: (rendered_sql, used_vars_set, template_params_list)
        
        Note: For MySQL, we replace {var} placeholders with %s and return params as a list.
        """
        if config.resource_mode != "SQL" or not config.custom_sql:
            return config.custom_sql or "", set(), []
        
        # Prepare Context & Params
        ctx = {}
        for f, op, v in query.filters:
            if f not in ctx:
                ctx[f] = v
        
        # Check for template tags first (optimization)
        if "{% " not in config.custom_sql and "{{" not in config.custom_sql:
            return config.custom_sql, set(), []
        
        # Analyze Template
        # Analyze Template
        # Use module-level env to avoid re-initialization overhead
        env = TEMPLATE_ENV
        try:
            ast = env.parse(config.custom_sql)
            undeclared = meta.find_undeclared_variables(ast)
            
            # Render
            template = env.from_string(config.custom_sql)
            rendered = template.render(**ctx)
            
            # Escape existing '%' to '%%' before adding our own '%s' placeholders
            # to avoid aiomysql/PyMySQL interpreting them as format characters.
            rendered = rendered.replace('%', '%%')

            # Replace {var} placeholders with %s for MySQL
            # and collect params in order
            template_params_list = []
            import re
            
            def replace_placeholder(match):
                var_name = match.group(1)
                # If variable is in context, use it
                if var_name in ctx:
                    template_params_list.append(self._clean_value(var_name, ctx[var_name]))
                    return "%s"
                # If variable is NOT in context (missing param), we have two choices:
                # 1. Raise error (Strict)
                # 2. Replace with NULL (Lenient)
                # For execute(), strict is usually better to avoid unexpected results.
                # But to avoid 500 syntax error, we raise a ValueError here.
                raise ValueError(f"Missing required parameter: {var_name}")
            
            # Replace {{ varname }} (Jinja2 DebugUndefined keeps the braces)
            # Note: DebugUndefined output might be {{ varname }} or {{ varname }}
            # We need a robust regex.
            rendered = re.sub(r'\{\{\s*(\w+)\s*\}\}', replace_placeholder, rendered)
            
            return rendered, undeclared, template_params_list
            
        except Exception as e:
            logger.error(f"Template rendering failed: {e}")
            raise ValueError(f"SQL Template Error: {e}. SQL: {config.custom_sql}")
    
    def _get_source_sql(self, config: ResourceResponse, rendered_sql: Optional[str] = None) -> str:
        """Determine FROM clause based on mode (TABLE or SQL)"""
        if config.resource_mode == "TABLE":
            return f"`{config.table_name}`"
        else:
            # Use rendered SQL if available, otherwise use original
            sql = rendered_sql if rendered_sql else config.custom_sql
            return f"({sql}) as subquery"
    

    def _build_where(self, query: LogicalQuery, config: ResourceResponse, exclude: Set[str] = None) -> tuple[str, tuple]:
        """
        Build WHERE clause with parameterized queries using %s placeholders.
        Returns: (where_sql, params_tuple)
        """
        allowed = [f.name for f in config.allowed_filters]
        where_parts = []
        params = []
        exclude = exclude or set()
        
        for f, op, v in query.filters:
            if f not in allowed or f in exclude:
                continue
            
            # Sanitize operator
            if op == "=":
                where_parts.append(f"`{f}` = %s")
                params.append(v)
            elif op == "IN":
                # For IN clause, create placeholders for each value
                if isinstance(v, (list, tuple)):
                    placeholders = ', '.join(['%s'] * len(v))
                    where_parts.append(f"`{f}` IN ({placeholders})")
                    params.extend(v)
            elif op in (">", "<", ">=", "<=", "!="):
                where_parts.append(f"`{f}` {op} %s")
                params.append(v)
            else:
                logger.warning(f"Unsupported operator: {op}")
                continue
        
        where_sql = " AND ".join(where_parts) if where_parts else "1=1"
        return where_sql, tuple(params)
    
    async def execute(self, query: LogicalQuery) -> ResultSet:
        """Execute query against MySQL"""
        from app.services.meta_service import MetaService
        config = await MetaService.get_config(query.resource)
        if not config:
            raise ValueError(f"Unknown resource: {query.resource}")
        
        from app.services.pool_manager import DataSourcePoolManager
        pool = await DataSourcePoolManager.get_pool(self.source_id)
        
        # Render Template
        rendered_sql, used_vars, template_params_list = self._render_sql(config, query)
        source = self._get_source_sql(config, rendered_sql)
        
        # Build Auto-Where (excluding vars used in template)
        where_sql, auto_params_tuple = self._build_where(query, config, exclude=used_vars)
        
        # Build SELECT fields
        select_fields = [f.name for f in config.fields_config]
        select_fields_str = ", ".join([f"`{f}`" for f in select_fields])
        
        # Build SQL with Safety Checks for Sort Field
        # 1. Validate sort_by against allowed fields to prevent injection
        sort_field = query.sort_by if (query.sort_by and query.sort_by in select_fields) else config.default_sort
        # 2. Strict validation for sort_order
        sort_order = "DESC" if query.sort_order.upper() == "DESC" else "ASC"
        
        offset = (query.page - 1) * query.size
        
        # Build SQL
        sql = f"""
            SELECT {select_fields_str}
            FROM {source}
            WHERE {where_sql}
            ORDER BY `{sort_field}` {sort_order}
            LIMIT %s OFFSET %s
        """
        
        # Merge params: template params (from {var} placeholders) + auto params + LIMIT/OFFSET
        final_params = tuple(template_params_list) + auto_params_tuple + (query.size, offset)
        
        async with pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                await cursor.execute(sql, final_params)
                rows = await cursor.fetchall()
        
        return ResultSet(
            items=[dict(row) for row in rows],
            total=len(rows),
            page=query.page,
            size=query.size,
            pages=(len(rows) + query.size - 1) // query.size if len(rows) > 0 else 0,
            generated_sql=sql.strip()
        )
    
    async def execute_summary(self, query: LogicalQuery, agg_fields: List[str]) -> Dict[str, Any]:
        """Execute aggregation query"""
        from app.services.meta_service import MetaService
        config = await MetaService.get_config(query.resource)
        if not config:
            raise ValueError(f"Unknown resource: {query.resource}")
        
        from app.services.pool_manager import DataSourcePoolManager
        pool = await DataSourcePoolManager.get_pool(self.source_id)
        
        # Render Template
        rendered_sql, used_vars, template_params_list = self._render_sql(config, query)
        source = self._get_source_sql(config, rendered_sql)
        
        # Build Auto-Where (excluding vars used in template)
        where_sql, auto_params_tuple = self._build_where(query, config, exclude=used_vars)
        
        # Build aggregation SQL
        agg_exprs = []
        for field in agg_fields:
            agg_exprs.append(f"COUNT(DISTINCT `{field}`) as `{field}_count`")
        
        sql = f"""
            SELECT {', '.join(agg_exprs)}
            FROM {source}
            WHERE {where_sql}
        """
        
        # Merge params: template params + auto params
        final_params = tuple(template_params_list) + auto_params_tuple
        
        async with pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                await cursor.execute(sql, final_params)
                result = await cursor.fetchone()
        
        return dict(result) if result else {}
    
    async def get_tables(self) -> List[Dict[str, str]]:
        """List all tables and views in the database with type"""
        from app.services.pool_manager import DataSourcePoolManager

        pool = await DataSourcePoolManager.get_pool(self.source_id)

        async with pool.acquire() as conn:
            async with conn.cursor() as cursor:
                # SHOW FULL TABLES returns (Table_name, Table_type)
                # Table_type: 'BASE TABLE', 'VIEW', 'SYSTEM VIEW'
                await cursor.execute("SHOW FULL TABLES")
                rows = await cursor.fetchall()

        return [
            {"name": row[0], "type": "VIEW" if "VIEW" in row[1].upper() else "TABLE"}
            for row in rows
        ]
    async def get_columns(self, table_name: Optional[str] = None, custom_sql: Optional[str] = None, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, str]]:
        """Get column information"""
        from app.services.pool_manager import DataSourcePoolManager
        # SqlLabUndefined class moved to module level for reuse

        pool = await DataSourcePoolManager.get_pool(self.source_id)
        
        if custom_sql:
            # Clean SQL
            raw_sql = custom_sql.strip()
            if raw_sql.endswith(";"):
                raw_sql = raw_sql[:-1]
                
            # Render Jinja2 template with provided params or dummy context
            # Render Jinja2 template with provided params or dummy context
            try:
                # Use custom undefined to keep SQL valid (e.g. WHERE col = NULL)
                env = SQL_LAB_ENV
                template = env.from_string(raw_sql)
                # Use provided params if available
                render_ctx = params if params is not None else {}
                sql = template.render(**render_ctx)
            except Exception as e:
                logger.warning(f"Template render failed during get_columns, using raw SQL: {e}")
                sql = raw_sql
                
            # Get columns from custom SQL (limit 0 for schema only)
            final_sql = f"SELECT * FROM ({sql}) as t LIMIT 0"
            async with pool.acquire() as conn:
                async with conn.cursor() as cursor:
                    try:
                        await cursor.execute(final_sql)
                        columns = [desc[0] for desc in cursor.description]
                    except Exception as e:
                        logger.error(f"Failed to fetch columns for MySQL: {e} SQL: {final_sql}")
                        raise ValueError(f"Invalid SQL or Table: {e}")
            return [{"name": col, "type": "String", "comment": ""} for col in columns]
        elif table_name:
            async with pool.acquire() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(
                        """
                        SELECT COLUMN_NAME, DATA_TYPE, COLUMN_COMMENT
                        FROM INFORMATION_SCHEMA.COLUMNS
                        WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s
                        ORDER BY ORDINAL_POSITION
                        """,
                        (table_name,),
                    )
                    rows = await cursor.fetchall()
            return [
                {"name": row[0], "type": row[1] or "String", "comment": row[2] or ""}
                for row in rows
            ]
        return []

    async def execute_sql(self, sql: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Execute raw SQL query with parameters.
        Returns: { "columns": [{"name": "...", "type": "..."}], "items": [[val1, val2], ...] }
        """
        from app.services.pool_manager import DataSourcePoolManager

        # aiomysql (like PyMySQL) runs ``query % escaped_args`` whenever args is not None.
        # A non-empty SQL containing literal ``%`` (e.g. ``LIKE '%中文%'``) then triggers Python's
        # %-formatter and can raise ValueError (e.g. "unsupported format character ... (0x4e34)").
        # Clients often send ``params: {}``; treat empty mapping as "no parameters" so plain SQL works.
        if params is not None and not params:
            params = None
        
        pool = await DataSourcePoolManager.get_pool(self.source_id)
        
        async with pool.acquire() as conn:
            # Use default cursor to get tuples (not dicts) to preserve order matching columns
            async with conn.cursor() as cursor:
                await cursor.execute(sql, params)
                rows = await cursor.fetchall()
                
                columns = []
                if cursor.description:
                    for desc in cursor.description:
                        # desc[0] is name, desc[1] is type_code
                        columns.append({"name": desc[0], "type": str(desc[1])})
                
                # Convert rows to list of lists
                items = [list(row) for row in rows]
                
                return {
                    "columns": columns,
                    "items": items
                }

    async def preview(self, sql: str, limit: int = 100, params: Dict[str, Any] = None, offset: int = 0, include_total: bool = False) -> Dict[str, Any]:
        """
        Safely execute a preview query for SQL Lab.
        Enforces row limits and read-only heuristic.
        Supports Jinja2 templating.
        """
        import time
        from jinja2 import Environment, BaseLoader
        from .base import SQLSafetyError
        
        params = params or {}
        
        # 1. Unified Safety Check
        try:
            self._validate_sql_safety(sql)
        except SQLSafetyError as e:
            raise ValueError(str(e))
        
        # 2. Render Template if needed
        rendered_sql = sql
        if "{{" in sql or "{%" in sql:
            try:
                # Use dedicated SQL Lab env to handle undefined variables gracefully
                template = SQL_LAB_ENV.from_string(sql)
                rendered_sql = template.render(**params)
                # Re-validate rendered SQL
                self._validate_sql_safety(rendered_sql)
            except SQLSafetyError as e:
                raise ValueError(str(e))
            except Exception as e:
                raise ValueError(f"Template rendering failed: {str(e)}")

        # 3. Limit Enforcement (Smart Check)
        clean_sql = rendered_sql.strip().rstrip(";")
        # If LIMIT is already specified, we trust the user.
        if "LIMIT" in clean_sql.upper():
            final_sql = clean_sql
        else:
            final_sql = f"SELECT * FROM ({clean_sql}) AS _preview_sub LIMIT {limit} OFFSET {offset}"
        
        start_time = time.perf_counter()
        
        from app.services.pool_manager import DataSourcePoolManager
        pool = await DataSourcePoolManager.get_pool(self.source_id)
        
        total_count = None
        async with pool.acquire() as conn:
            async with conn.cursor() as cursor:
                if include_total and "LIMIT" not in clean_sql.upper():
                    count_sql = f"SELECT COUNT(*) AS _cnt FROM ({clean_sql}) AS _preview_cnt"
                    await cursor.execute(count_sql)
                    count_row = await cursor.fetchone()
                    total_count = int(count_row[0]) if count_row else 0

                logger.info(f"Executing MySQL Preview SQL: {final_sql} with params {params}")
                
                await cursor.execute(final_sql)
                rows = await cursor.fetchall()
                
                columns = []
                if cursor.description:
                    for desc in cursor.description:
                         columns.append({"name": desc[0], "type": str(desc[1])})
                
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
        from .base import SQLSafetyError

        params = params or {}
        try:
            self._validate_sql_safety(sql)
        except SQLSafetyError as e:
            raise ValueError(str(e))

        rendered_sql = sql
        if "{{" in sql or "{%" in sql:
            template = SQL_LAB_ENV.from_string(sql)
            rendered_sql = template.render(**params)
            self._validate_sql_safety(rendered_sql)

        clean_sql = rendered_sql.strip().rstrip(";")
        if clean_sql.upper().startswith("EXPLAIN"):
            explain_sql = clean_sql
        else:
            explain_sql = f"EXPLAIN {clean_sql}"

        start_time = time.perf_counter()
        from app.services.pool_manager import DataSourcePoolManager
        pool = await DataSourcePoolManager.get_pool(self.source_id)
        async with pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(explain_sql)
                rows = await cursor.fetchall()
                columns = [{"name": desc[0], "type": str(desc[1])} for desc in cursor.description] if cursor.description else []

        return {
            "columns": columns,
            "rows": [list(r) for r in rows],
            "execution_time_ms": (time.perf_counter() - start_time) * 1000,
        }

