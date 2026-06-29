from typing import Any, Dict, List, Optional, Tuple, Set
from .base import DataSourceAdapter
from .models import LogicalQuery, ResultSet
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from asynch.errors import InterfaceError
import logging
from app.schemas.resource import ResourceResponse
from jinja2 import Environment, BaseLoader, meta
from functools import lru_cache
from app.utils.jinja_sql import SQL_LAB_ENV

logger = logging.getLogger(__name__)

# Global Jinja2 Environment with built-in cache
_JINJA_ENV = Environment(loader=BaseLoader(), autoescape=False, cache_size=512)
_SQL_LAB_ENV = SQL_LAB_ENV

@lru_cache(maxsize=512)
def _parse_template(sql_template: str) -> Tuple[Any, Set[str]]:
    """
    Parse SQL template and return (Template Object, Undeclared Variables).
    Cached to avoid re-parsing AST on every request.
    """
    try:
        ast = _JINJA_ENV.parse(sql_template)
        undeclared = meta.find_undeclared_variables(ast)
        template = _JINJA_ENV.from_string(sql_template)
        return template, undeclared
    except Exception as e:
        logger.error(f"Template parsing failed: {e}")
        raise ValueError(f"SQL Template Error: {e}")

class ClickHouseAdapter(DataSourceAdapter):
    """ClickHouse Adapter using Native Protocol (asynch) with dynamic data source support"""
    
    def __init__(self, source_id: int):
        """Initialize adapter with data source ID"""
        self.source_id = source_id

    def _clean_value(self, field: str, value: Any) -> Any:
        """Helper to sanitize/convert values (e.g. timestamps)"""
        clean_v = value
        # Special handling for metric_time: always ensure it's a timestamp
        if field in ("metric_time", "event_time"):
            if isinstance(value, str) and ("-" in value or ":" in value):
                try:
                    from datetime import datetime
                    dt_str = value.replace("T", " ")
                    dt = datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S")
                    clean_v = int(dt.timestamp())
                except ValueError:
                    pass 
        return clean_v
    
    def _build_where(self, query: LogicalQuery, config: ResourceResponse, exclude: Set[str] = None) -> tuple[str, Dict[str, Any]]:
        """
        Helper to build WHERE clause with secure parameter binding.
        Returns: (where_sql, parameters_dict)
        """
        allowed = [f.name for f in config.allowed_filters]
        where_parts = []
        params = {}
        exclude = exclude or set()
        
        for i, (f, op, v) in enumerate(query.filters):
            if f not in allowed:
                continue
            
            # Skip if this field is handled by Custom SQL template
            if f in exclude:
                continue
            
            # Generate unique parameter name to avoid collisions if multiple filters use same column
            param_name = f"{f}_{i}"
            
            clean_v = self._clean_value(f, v)
            
            if op == ">=":
                where_parts.append(f"{f} >= {{{param_name}}}")
                params[param_name] = clean_v
            elif op == ">":
                where_parts.append(f"{f} > {{{param_name}}}")
                params[param_name] = clean_v
            elif op == "<=":
                where_parts.append(f"{f} <= {{{param_name}}}")
                params[param_name] = clean_v
            elif op == "<":
                where_parts.append(f"{f} < {{{param_name}}}")
                params[param_name] = clean_v
            elif op == "=":
                where_parts.append(f"{f} = {{{param_name}}}")
                params[param_name] = clean_v
            elif op == "!=":
                where_parts.append(f"{f} != {{{param_name}}}")
                params[param_name] = clean_v
            elif op.upper() == "LIKE":
                where_parts.append(f"{f} LIKE {{{param_name}}}")
                params[param_name] = clean_v
            elif op.upper() == "IN":
                 if isinstance(clean_v, (list, tuple)):
                     where_parts.append(f"{f} IN {{{param_name}}}")
                     params[param_name] = tuple(clean_v) if isinstance(clean_v, list) else clean_v
                 else:
                     where_parts.append(f"{f} IN {{{param_name}}}")
                     params[param_name] = (clean_v,)
            
        where_sql = " AND ".join(where_parts) if where_parts else "1=1"
        return where_sql, params

    def _process_row(self, row: tuple, fields: List[str]) -> Dict[str, Any]:
        """Convert a DB row tuple to a dictionary, ensuring string format for Pydantic compatibility."""
        item = {}
        for i, field in enumerate(fields):
            val = row[i]
            # Consistent with schema requirements: everything is Optional[str] or str
            if val is not None:
                item[field] = str(val)
            else:
                item[field] = None
        return item

    def _render_sql(self, config: ResourceResponse, query: LogicalQuery) -> Tuple[str, Set[str], Dict[str, Any]]:
        """
        Render Custom SQL using Jinja2 if applicable.
        Returns: (rendered_sql, used_vars_set, template_params)
        """
        if config.resource_mode != "SQL" or not config.custom_sql:
            return config.custom_sql or "", set(), {}

        # 1. Prepare Context & Params
        # We assume one value per field for template injection (taking the first one found)
        # This mirrors standard Key-Value usage.
        ctx = {}
        for f, op, v in query.filters:
            # We use the raw value for Jinja context (logic), but cleaned value for DB params
            if f not in ctx:
                 ctx[f] = v

        # 2. Analyze & Render (Cached)
        try:
            # Optimization: check for tags first
            if "{%" not in config.custom_sql and "{{" not in config.custom_sql:
                return config.custom_sql, set(), {}
            
            # Use cached parser
            from jinja2 import StrictUndefined
            # Use StrictUndefined to raise error if param is missing
            template, undeclared = _parse_template(config.custom_sql)
            template.environment.undefined = StrictUndefined
            
            rendered = template.render(**ctx)
            
            # 3. Prepare DB Params for the used variables
            template_params = {}
            for var in undeclared:
                if var in ctx:
                    template_params[var] = self._clean_value(var, ctx[var])
            
            return rendered, undeclared, template_params
            
        except ValueError as e:
            raise e
        except Exception as e:
            # Jinja2 UndefinedError will be caught here
            if "is undefined" in str(e):
                raise ValueError(f"Missing required parameter: {e}. SQL: {config.custom_sql}")
            logger.error(f"Template rendering failed: {e}")
            raise ValueError(f"SQL Template Error: {e}. SQL: {config.custom_sql}")

    def _get_source_sql(self, config: ResourceResponse, rendered_sql: Optional[str] = None) -> str:
        """Determine FROM clause based on mode (TABLE or SQL)"""
        if config.resource_mode == "SQL":
            sql = rendered_sql if rendered_sql is not None else config.custom_sql
            # Strip trailing semicolon if present to avoid syntax error in subquery
            sql = sql.strip()
            if sql.endswith(";"):
                sql = sql[:-1]
            return f"({sql}) AS _sub"
        else:
            return config.table_name

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=0.5, min=0.5, max=5),
        retry=retry_if_exception_type((InterfaceError, OSError))
    )
    async def execute(self, query: LogicalQuery) -> ResultSet:
        from app.services.meta_service import MetaService
        config = await MetaService.get_config(query.resource)
        if not config:
            raise ValueError(f"Unknown resource: {query.resource}")

        fields = [f.name for f in config.fields_config]
        default_sort = config.default_sort
        allowed_filters = [f.name for f in config.allowed_filters]
        
        # Render Template
        rendered_sql, used_vars, template_params = self._render_sql(config, query)
        source = self._get_source_sql(config, rendered_sql)

        # Build Auto-Where (excluding vars used in template)
        where_sql, auto_params = self._build_where(query, config, exclude=used_vars)
        
        # Merge params
        final_params = {**auto_params, **template_params}

        # Execute queries
        try:
            from app.services.pool_manager import DataSourcePoolManager
            pool = await DataSourcePoolManager.get_pool(self.source_id)
            
            # Session settings to prevent runaway queries
            query_settings = {
                "max_execution_time": 20,           # Limit query to 20 seconds
                "max_memory_usage": 4294967296,     # Limit memory usage to 4GB
                "max_rows_to_read": 1000000000,     # Limit total rows to read to 1B
                "connect_timeout": 5,
                "send_timeout": 30,
                "receive_timeout": 30
            }

            async with pool.connection() as conn:
                # Construct SETTINGS clause
                settings_clause = ""
                if query_settings:
                    settings_list = [f"{k}={v}" for k, v in query_settings.items()]
                    settings_clause = " SETTINGS " + ", ".join(settings_list)

                # Count Total
                async with conn.cursor() as cursor:
                    # Log query for debugging
                    count_sql = f"SELECT COUNT(*) FROM {source} WHERE {where_sql}"
                    final_count_sql = count_sql + settings_clause
                    
                    logger.info(f"Executing ClickHouse Total Count: {count_sql} with params {final_params}")
                    
                    # Pass params ONLY (settings appended to SQL)
                    await cursor.execute(final_count_sql, final_params)
                    total_row = await cursor.fetchone()
                    total = total_row[0]

                # Fetch Data
                sort_field = query.sort_by if (query.sort_by and query.sort_by in allowed_filters) else default_sort
                offset = (query.page - 1) * query.size
                select_fields_str = ", ".join(fields)

                # Validation for sort_order to prevent injection (though it's enum in pydantic, good to be safe)
                sort_order = "DESC" if query.sort_order.upper() == "DESC" else "ASC"

                # Standard SQL construction with placeholders for WHERE parameters
                # LIMIT and OFFSET are integers controlled by Pydantic model, safe to interpolate
                base_sql = f"""
                    SELECT {select_fields_str}
                    FROM {source}
                    WHERE {where_sql}
                    ORDER BY {sort_field} {sort_order}
                    LIMIT {query.size} OFFSET {offset}
                """
                
                final_sql = base_sql + settings_clause
                
                async with conn.cursor() as cursor: 
                    logger.info(f"Executing ClickHouse Data Query: {base_sql} with params {final_params}")
                    await cursor.execute(final_sql, final_params)
                    rows = await cursor.fetchall()
                
                items = [self._process_row(row, fields) for row in rows]
        except Exception as e:
            # Catch ClickHouse parse errors (e.g. invalid date) and return as 400 via ValueError
            err_msg = str(e)
            if "Cannot parse" in err_msg or "syntax error" in err_msg.lower():
                raise ValueError(f"Invalid query parameters or datetime format: {err_msg}")
            raise e

        pages = (total + query.size - 1) // query.size
        return ResultSet(
            items=items, 
            total=total, 
            page=query.page, 
            size=query.size, 
            pages=pages,
            generated_sql=base_sql.strip()
        )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=0.5, min=0.5, max=5),
        retry=retry_if_exception_type((InterfaceError, OSError))
    )
    async def execute_summary(self, query: LogicalQuery) -> Dict[str, Any]:
        """Calculate aggregation summary (AVG, MIN, MAX) for metric_value"""
        from app.services.meta_service import MetaService
        config = await MetaService.get_config(query.resource)
        if not config:
            raise ValueError(f"Unknown resource: {query.resource}")
        
        # Render Template
        rendered_sql, used_vars, template_params = self._render_sql(config, query)
        source = self._get_source_sql(config, rendered_sql)
        
        where_sql, auto_params = self._build_where(query, config, exclude=used_vars)
        final_params = {**auto_params, **template_params}
        
        query_settings = {
            "max_execution_time": 20,
            "max_memory_usage": 4294967296,
            "max_rows_to_read": 1000000000
        }

        # Note: metric_value is String in DB, need cast to Float64
        sql = f"""
            SELECT 
                avg(toFloat64OrZero(metric_value)) as avg_val,
                min(toFloat64OrZero(metric_value)) as min_val,
                max(toFloat64OrZero(metric_value)) as max_val,
                count() as count
            FROM {source}
            WHERE {where_sql}
        """
        
        # Construct SETTINGS clause
        if query_settings:
            settings_list = [f"{k}={v}" for k, v in query_settings.items()]
            sql += " SETTINGS " + ", ".join(settings_list)
        
        from app.services.pool_manager import DataSourcePoolManager
        pool = await DataSourcePoolManager.get_pool(self.source_id)
        
        async with pool.connection() as conn:
            async with conn.cursor() as cursor:
                logger.info(f"Executing ClickHouse Summary: {sql} with params {final_params}")
                await cursor.execute(sql, final_params) 
                row = await cursor.fetchone() # (avg, min, max, count)
            
            return {
                "average_temperature": row[0] if row[0] is not None else 0.0,
                "min_temperature": row[1] if row[1] is not None else 0.0,
                "max_temperature": row[2] if row[2] is not None else 0.0,
                "count": row[3]
            }

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=0.5, min=0.5, max=5),
        retry=retry_if_exception_type((InterfaceError, OSError))
    )
    async def get_tables(self) -> List[Dict[str, str]]:
        """Fetch all table names from the current database with type info."""
        from app.services.pool_manager import DataSourcePoolManager
        pool = await DataSourcePoolManager.get_pool(self.source_id)
        
        async with pool.connection() as conn:
            async with conn.cursor() as cursor:
                # Query system.tables to get table name and engine type
                # engine: 'View', 'MaterializedView', 'MergeTree', etc.
                sql = "SELECT name, engine FROM system.tables WHERE database = currentDatabase() ORDER BY name"
                await cursor.execute(sql)
                rows = await cursor.fetchall()
                
                return [
                    {"name": row[0], "type": "VIEW" if "VIEW" in row[1].upper() else "TABLE"}
                    for row in rows
                ]

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=0.5, min=0.5, max=5),
        retry=retry_if_exception_type((InterfaceError, OSError))
    )
    async def get_columns(self, table_name: Optional[str] = None, custom_sql: Optional[str] = None, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, str]]:
        """Fetch columns for a table or custom SQL query. Returns list of {name, type}."""
        if custom_sql:
            raw_sql = custom_sql
            try:
                # Use custom undefined to keep SQL valid (e.g. WHERE col = NULL)
                env = _SQL_LAB_ENV
                template = env.from_string(raw_sql)
                # Use provided params if available
                render_ctx = params if params is not None else {}
                sql = template.render(**render_ctx)
            except Exception as e:
                logger.warning(f"Template processing failed during get_columns, using raw SQL: {e}")
                sql = raw_sql

            # Use ClickHouse 'DESCRIBE (subquery)' feature
            query = f"DESCRIBE ({sql})"
        else:
            query = f"DESCRIBE {table_name}"
        
        from app.services.pool_manager import DataSourcePoolManager
        pool = await DataSourcePoolManager.get_pool(self.source_id)
        
        async with pool.connection() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(query)
                rows = await cursor.fetchall()
                # rows format: (name, type, default_type, default_expression, comment, codec_expression, ttl_expression)
                return [{"name": row[0], "type": row[1], "comment": row[4]} for row in rows]

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=0.5, min=0.5, max=5),
        retry=retry_if_exception_type((InterfaceError, OSError))
    )
    async def execute_sql(self, sql: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Execute raw SQL query with parameters.
        Returns: { "columns": [{"name": "...", "type": "..."}], "items": [[val1, val2], ...] }
        """
        from app.services.pool_manager import DataSourcePoolManager
        pool = await DataSourcePoolManager.get_pool(self.source_id)
        
        async with pool.connection() as conn:
            async with conn.cursor() as cursor:
                logger.info(f"Executing Raw ClickHouse SQL: {sql} with params {params}")
                await cursor.execute(sql, params)
                rows = await cursor.fetchall()
                
                # Get column info from cursor.description
                # clickhouse-driver/asynch description: (name, type, display_size, internal_size, precision, scale, null_ok)
                columns = []
                if cursor.description:
                    for desc in cursor.description:
                         columns.append({"name": desc[0], "type": desc[1]})
                         
                # Convert rows (tuples) to lists for JSON consistency (and easier mutation if needed)
                items = [list(row) for row in rows]
                
                return {
                    "columns": columns,
                    "items": items
                }

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=0.5, min=0.5, max=5),
        retry=retry_if_exception_type((InterfaceError, OSError))
    )
    async def preview(self, sql: str, limit: int = 100, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Safely execute a preview query for SQL Lab.
        Enforces read-only mode and row limits.
        Supports Jinja2 templating for variables.
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
                template = _SQL_LAB_ENV.from_string(sql)
                rendered_sql = template.render(**params)
                # Re-validate rendered SQL
                self._validate_sql_safety(rendered_sql)
            except SQLSafetyError as e:
                raise ValueError(str(e))
            except Exception as e:
                raise ValueError(f"Template rendering failed: {str(e)}")

        # 3. Limit Enforcement (Smart Check)
        clean_sql = rendered_sql.strip().rstrip(";")
        # If LIMIT is already specified, we trust the user or just append our limit if needed.
        # However, to avoid subquery optimization issues in CH, we only wrap if it's a simple query.
        if "LIMIT" in clean_sql.upper():
            final_sql = clean_sql
        else:
            final_sql = f"SELECT * FROM ({clean_sql}) LIMIT {limit}"
        
        start_time = time.perf_counter()
        
        from app.services.pool_manager import DataSourcePoolManager
        pool = await DataSourcePoolManager.get_pool(self.source_id)
        
        # 4. Execution with Restricted Settings
        query_settings = {
            "max_execution_time": 10,           # Max 10s for preview
            "max_rows_to_read": 0,              # Disable scan row limit for preview as we have outer LIMIT
            "readonly": 1                       # ClickHouse readonly mode
        }
        
        settings_clause = " SETTINGS " + ", ".join([f"{k}={v}" for k, v in query_settings.items()])
        final_sql += settings_clause
        
        async with pool.connection() as conn:
            async with conn.cursor() as cursor:
                logger.info(f"Executing Preview SQL: {final_sql} with params {params}")
                await cursor.execute(final_sql)
                rows = await cursor.fetchall()
                
                columns = []
                if cursor.description:
                    for desc in cursor.description:
                         columns.append({"name": desc[0], "type": desc[1]})
                
                # Rows to list
                items = [list(row) for row in rows]
                
        execution_time = (time.perf_counter() - start_time) * 1000
        
        return {
            "columns": columns,
            "rows": items,
            "execution_time_ms": execution_time,
            "scanned_rows": 0
        }

