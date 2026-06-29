from fastapi import APIRouter, Depends, HTTPException, Body, BackgroundTasks, Response
from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional, Union
import logging
import time
import uuid
import re
import sqlparse

from app.services.auth_service import AuthService
from app.services.meta_service import MetaService
from app.services.datasource_service import DataSourceService
from app.services.data_adapter.factory import get_adapter
from app.services.data_adapter.base import SQLSafetyError
from app.core.errors import ErrorCode
from app.core import database

# Define Router
router = APIRouter()
logger = logging.getLogger(__name__)

# Constants
PERMISSION_KEY = "system.sql.execute"
DEFAULT_LIMIT = 1000
MAX_LIMIT = 10000

# Models
class SqlExecutionRequest(BaseModel):
    data_source: Union[int, str] = Field(..., description="Target Data Source ID or Name")
    sql: str = Field(..., description="Raw SQL Query (SELECT only)")
    params: Optional[Dict[str, Any]] = Field(None, description="Optional parameters for binding")
    cache_ttl: Optional[int] = Field(None, description="Cache TTL in seconds (None=Use System Default, 0=Disabled)")

class ColumnMeta(BaseModel):
    name: str
    type: str

class SqlExecutionData(BaseModel):
    columns: List[ColumnMeta]
    items: List[List[Any]]

class SqlExecutionResponse(BaseModel):
    code: int = 200
    message: str = "success"
    data: SqlExecutionData

# Helpers
from app.core.dependencies import require_api_key, check_rate_limit
from app.services.permission_service import PermissionService

# Helpers
async def _verify_permission(user: Dict = Depends(require_api_key)):
    # 1. Admin Bypass
    if user.get("role") == "admin":
        return user

    # 2. Strict Check for others
    user_id = int(user["user_id"])
    
    # 获取详细权限 (包含缓存)
    user_perms = await PermissionService.get_user_permissions(user_id)
    
    # 基础权限校验
    if PERMISSION_KEY not in user_perms.permissions.resources:
        raise HTTPException(status_code=403, detail="Permission Denied: Missing system.sql.execute")
        
    # 返回包含权限的对象
    user["permissions"] = user_perms.permissions
    return user

from app.utils.sql_parser import extract_table_names

def _enforce_limit(sql: str, source_type: str = "mysql") -> str:
    """
    Smartly ensure SELECT/WITH queries have a LIMIT clause using sqlparse.
    Supports different syntaxes:
    - MySQL/ClickHouse: LIMIT {n}
    - Oracle: FETCH FIRST {n} ROWS ONLY
    """
    try:
        formatted_sql = sqlparse.format(sql, strip_comments=True).strip()
        parsed = sqlparse.parse(formatted_sql)
        if not parsed: return sql
        
        stmt = parsed[0]
        first_token = stmt.token_first(skip_cm=True, skip_ws=True)
        if not first_token: return sql
        
        keyword = first_token.value.upper()
        
        # Only enforce LIMIT on SELECT and WITH
        if keyword not in ("SELECT", "WITH"):
             return sql

        # 1. Check if limit already exists
        has_limit = False
        if source_type == "oracle":
            # Check for FETCH FIRST/NEXT
            sql_upper = sql.upper()
            if "FETCH FIRST" in sql_upper or "FETCH NEXT" in sql_upper or "ROWNUM" in sql_upper:
                has_limit = True
        else:
            # Check for LIMIT keyword (MySQL/ClickHouse)
            for token in stmt.flatten():
                 if token.ttype == sqlparse.tokens.Keyword and token.value.upper() == 'LIMIT':
                     has_limit = True
                     break
        
        if has_limit:
            return sql
            
        # 2. Append appropriate Limit syntax
        if source_type == "oracle":
            # Handle trailing semicolon
            stripped_sql = sql.strip()
            if stripped_sql.endswith(';'):
                stripped_sql = stripped_sql[:-1]
            
            # Wrap with ROWNUM for maximum compatibility (11g and 12c)
            # This also ensures correctly applying limits after ORDER BY in the subquery
            return f"SELECT * FROM ({stripped_sql}) WHERE ROWNUM <= {DEFAULT_LIMIT}"
        else:
            limit_clause = f" LIMIT {DEFAULT_LIMIT}"
            # Handle trailing semicolon
            stripped_sql = sql.strip()
            if stripped_sql.endswith(';'):
                return stripped_sql[:-1] + f"{limit_clause};"
            else:
                return f"{stripped_sql}{limit_clause}"
            
    except Exception:
        # Fallback to simple regex/string check as last resort backup
        if source_type == "oracle":
            if "FETCH FIRST" not in sql.upper() and "ROWNUM" not in sql.upper():
                 return f"SELECT * FROM ({sql}) WHERE ROWNUM <= {DEFAULT_LIMIT}"
        else:
            if not re.search(r'\bLIMIT\s+\d+', sql, re.IGNORECASE):
                 return f"{sql} LIMIT {DEFAULT_LIMIT}"
        return sql

async def _insert_audit_log(user_id: int, data_source_id: int, sql: str, duration_ms: float, status: str, error: str = None, action_type: str = 'SQL_EXECUTE'):
    """Insert audit log into sys_api_audit_log"""
    try:
        async with database.get_db_connection() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute("""
                    INSERT INTO sys_api_audit_log 
                    (user_id, data_source_id, generated_sql, execution_time_ms, status, action_type, error_message)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (user_id, data_source_id, sql, duration_ms, status, action_type, error))
                await conn.commit()
    except Exception as e:
        logger.error(f"Failed to write audit log: {e}")

# Endpoint
@router.post("/execute", summary="动态 SQL 查询") # Removed response_model to allow returning Response directly without re-validation
async def execute_sql(
    request: SqlExecutionRequest, 
    background_tasks: BackgroundTasks,
    user: Dict = Depends(_verify_permission),
    _rate_limit: None = Depends(check_rate_limit)
):
    """
    执行动态 SQL 查询。
    
    **使用说明**:
    1. **数据源**: 通过 `data_source` 指定目标数据库。
    2. **安全性**: 仅支持 `SELECT`, `SHOW`, `DESCRIBE`, `EXPLAIN`。查询会自动追加 `LIMIT 1000`。
    3. **缓存**: 可选 `cache_ttl` 参数 (秒)。
    4. **权限**: 必须拥有 `system.sql.execute` 资源权限。
    """
    start_time = time.time()
    user_id = int(user["user_id"])
    final_sql = request.sql
    error_msg = None
    status = "SUCCESS"
    actual_ds_id = 0
    cache_key = None
    
    # Resolve TTL
    final_cache_ttl = request.cache_ttl
    if final_cache_ttl is None:
        # Fetch system default
        try:
            sys_config = await MetaService.get_config(PERMISSION_KEY)
            final_cache_ttl = sys_config.cache_ttl if sys_config else 30
        except Exception:
            final_cache_ttl = 30
            
    # Cache Logic Check
    from app.core import redis
    import hashlib
    import json
    
    try:
        # 1. Get Data Source
        if isinstance(request.data_source, int):
            datasource = await DataSourceService.get_datasource(request.data_source)
        else:
            datasource = await DataSourceService.get_datasource_by_name(request.data_source)
            
        if not datasource:
             raise HTTPException(status_code=404, detail=f"Data source '{request.data_source}' not found")
             
        # Track ID for audit log
        actual_ds_id = datasource.id
        ds_name = datasource.source_name

        # --- Granular Permission Check ---
        if user.get("role") != "admin":
            perms = user.get("permissions")
            if not perms:
                raise HTTPException(status_code=403, detail="Permission Denied: No permissions loaded")

            # A. 校验数据源权限 (ds:name)
            ds_perm_key = f"ds:{ds_name}"
            if ds_perm_key not in perms.datasources:
                logger.warning(f"DS Access Denied | User: {user_id} | DS: {ds_name}")
                raise HTTPException(status_code=403, detail=f"Permission Denied: No access to data source '{ds_name}'")

            # B. 校验数据表权限
            # 策略：空=拒绝, ALL(*)=全通, 具体的=白名单
            tables = extract_table_names(request.sql)
            
            # 检查是否有显式全通权限 ds:name:table:*
            all_tables_key = f"ds:{ds_name}:table:*"
            if all_tables_key not in perms.data_tables:
                # 进入白名单校验模式
                allowed_tables = [p.split(":table:")[-1] for p in perms.data_tables if p.startswith(f"ds:{ds_name}:table:")]
                
                # 如果既没有全通权限，白名单也为空 -> 拒绝访问任何表
                if not allowed_tables:
                    logger.warning(f"Table Access Denied (Empty Policy) | User: {user_id} | DS: {ds_name}")
                    raise HTTPException(status_code=403, detail=f"Permission Denied: No tables authorized for data source '{ds_name}'")

                # 检查 SQL 中的每一张表
                for t in tables:
                    if t not in allowed_tables:
                        # 尝试检查带前缀的匹配 (db.table)
                        # 如果用户授权的是 tableA，但查询是 select * from db.tableA
                        if not any(at == t or t.endswith(f".{at}") for at in allowed_tables):
                            logger.warning(f"Table Access Denied | User: {user_id} | Table: {t} | Allowed: {allowed_tables}")
                            raise HTTPException(status_code=403, detail=f"Permission Denied: No access to table '{t}' in '{ds_name}'")
        # ---------------------------------

        # 2. Get Adapter and Perform Safety Check
        adapter = await get_adapter(datasource.source_name)
        
        # Use centralized safety check from base adapter
        try:
            adapter._validate_sql_safety(request.sql)
        except SQLSafetyError as e:
            # Special handling for Security Violations
            status = "SECURITY_VIOLATION"
            error_msg = str(e)
            logger.warning(f"SQL Security Violation | User: {user_id} | Error: {error_msg}")
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))
            
        # 3. Limit Enforcement (Smart)
        final_sql = _enforce_limit(request.sql, datasource.source_type)
        
        # --- Cache Read ---

        if final_cache_ttl and final_cache_ttl > 0:
            try:
                # Cache Key same as before
                param_str = json.dumps(request.params, sort_keys=True) if request.params else ""
                unique_str = f"{actual_ds_id}:{final_sql}:{param_str}"
                query_hash = hashlib.md5(unique_str.encode()).hexdigest()
                cache_key = f"yunshu:sql_exec:{query_hash}"
                
                r = await redis.get_redis()
                if r:
                    cached = await r.get(cache_key)
                    if cached:
                        # cached is already a JSON string. Return it directly!
                        # Construct a manual response structure as expected by client
                        # Client expects {code: 200, message: "success", data: ...}
                        # The cached content is just the `data` part (dict of result).
                        # So we need to wrap it.
                        # Wait, writing logic below says `json.dumps(result)`. 
                        # We should verify what exactly is cached. Yes, `result` dict.
                        
                        # Optimization: We construct the final JSON string manually to avoid parsing cached JSON
                        final_json = f'{{"code": 200, "message": "success", "data": {cached}}}'
                        
                        # Logging and Audit
                        status = "SUCCESS (CACHE)"
                        logger.info(f"SQL Cache HIT | User: {user_id} | Key: {cache_key}")
                        
                        return Response(content=final_json, media_type="application/json", headers={"X-Cache": "HIT"})
                        
            except Exception as e:
                logger.warning(f"Cache read error: {e}")
        # ------------------
             
        # 4. Get Adapter
        adapter = await get_adapter(datasource.source_name)
        
        # 5. Execute
        result = await adapter.execute_sql(final_sql, request.params)
        
        # 6. Serialization (Optimize: Do it ONCE)
        # Use default=str to safely handle Dates/Decimals
        result_json_str = json.dumps(result, default=str)
        
        # --- Cache Write ---
        if cache_key and final_cache_ttl and final_cache_ttl > 0:
            try:
                r = await redis.get_redis()
                if r:
                    await r.setex(cache_key, final_cache_ttl, result_json_str)
            except Exception as e:
                logger.warning(f"Cache write error: {e}")
        # -------------------
        
        # 7. Return Direct Response
        # Wrap in Standard Response Format
        final_response_json = f'{{"code": 200, "message": "success", "data": {result_json_str}}}'
        
        status = "SUCCESS (DB)"
        logger.info(f"SQL Cache MISS | User: {user_id} | DB Exec Time: {(time.time() - start_time)*1000:.2f}ms")
        
        # Attach background tasks to response
        return Response(content=final_response_json, media_type="application/json", headers={"X-Cache": "MISS"}, background=background_tasks)
        
    except Exception as e:
        status = "FAILED"
        error_msg = str(e)
        logger.error(f"SQL Execution Failed: {e}")
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=400, detail=f"Database Error: {error_msg}")
        
    finally:
        # 8. Async Audit Log
        duration = (time.time() - start_time) * 1000
        background_tasks.add_task(
            _insert_audit_log, user_id, actual_ds_id, final_sql, duration, status, error_msg
        )