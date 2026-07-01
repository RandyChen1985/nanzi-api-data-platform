from fastapi import APIRouter, Depends, HTTPException, Body, Request
from typing import List, Dict, Any, Optional
from app.core.dependencies import require_admin, require_api_key, require_permission
from app.core.database import get_db_connection
from app.services.ai_service import AIService
from app.services.vector_service import VectorService
from app.services.platform_settings_service import PlatformSettingsService
from app.services.dingtalk_notification_service import DingTalkNotificationService
from app.schemas.platform_settings import (
    PlatformSettingsResponse,
    PlatformSettingsUpdate,
    DingTalkPlatformSettings,
    McpPlatformSettingsUpdate,
    McpTestResponse,
)
from app.services.mcp_test_service import McpTestService
from app.core.redis import get_redis
from pydantic import BaseModel
import logging
import asyncio

router = APIRouter()
logger = logging.getLogger(__name__)

# --- Models ---
class ConfigUpdate(BaseModel):
    configs: Dict[str, str]

class PurgeRequest(BaseModel):
    days: int = 30

# --- 1. General Config Endpoints (Restored) ---

@router.get("/config")
async def get_system_config(user=Depends(require_permission("element:config:save"))):
    """Get all system configuration items"""
    config = {}
    async with get_db_connection() as db:
        async with db.cursor() as cursor:
            await cursor.execute("SELECT config_key, config_value FROM sys_config")
            rows = await cursor.fetchall()
            for row in rows:
                config[row[0]] = row[1]
    return config

@router.post("/config")
async def update_system_config(payload: Dict[str, str], user=Depends(require_permission("element:config:save"))):
    """Update general configuration items"""
    async with get_db_connection() as db:
        async with db.cursor() as cursor:
            for key, value in payload.items():
                await cursor.execute(
                    "UPDATE sys_config SET config_value = %s WHERE config_key = %s",
                    (value, key)
                )
                
                # 清理 Redis 缓存
                try:
                    redis_client = await get_redis()
                    if redis_client:
                        # 兼容 SystemService 的缓存键格式
                        await redis_client.delete(f"yunshu:config:{key}")
                except Exception as e:
                    logger.warning(f"Failed to invalidate cache for {key}: {e}")
                    
    return {"message": "Configuration updated successfully"}


@router.get("/platform-settings", response_model=PlatformSettingsResponse)
async def get_platform_settings(
    request: Request,
    user=Depends(require_permission("element:config:save")),
):
    """平台业务配置：数据产品目录、钉钉通知等"""
    return await PlatformSettingsService.get_settings(str(request.base_url).rstrip("/"))


@router.put("/platform-settings", response_model=PlatformSettingsResponse)
async def update_platform_settings(
    request: Request,
    body: PlatformSettingsUpdate,
    user=Depends(require_permission("element:config:save")),
):
    return await PlatformSettingsService.update_settings(
        body,
        request_base_url=str(request.base_url).rstrip("/"),
    )


@router.post("/platform-settings/dingtalk/test")
async def test_dingtalk_platform_settings(
    body: Optional[DingTalkPlatformSettings] = Body(None),
    user=Depends(require_permission("element:config:save")),
):
    override = body.model_dump() if body else None
    ok, detail = await DingTalkNotificationService.send_test_message(override)
    if not ok:
        raise HTTPException(status_code=400, detail=detail or "钉钉通知发送失败")
    return {"success": True}


@router.post("/platform-settings/mcp/test", response_model=McpTestResponse)
async def test_mcp_platform_settings(
    request: Request,
    body: Optional[McpPlatformSettingsUpdate] = Body(None),
    user=Depends(require_permission("element:config:save")),
):
    """探测 MCP SDK、状态探针与 SSE 端点（支持未保存的表单值）。"""
    override = body.model_dump() if body else None
    local_base = str(request.base_url).rstrip("/")
    _ok, result = await McpTestService.run_test(override, local_base_url=local_base)
    return result

# --- 2. AI Config Endpoints ---

@router.get("/config/ai/debug")
async def debug_ai_config(user=Depends(require_admin)):
    """Debug endpoint to see raw database values for AI config"""
    async with get_db_connection() as db:
        async with db.cursor() as cursor:
            await cursor.execute("SELECT config_value FROM sys_config WHERE config_key = 'ai.enabled'")
            row = await cursor.fetchone()
            return {"raw_value": row[0] if row else "NOT_FOUND"}

@router.get("/config/ai")
async def get_ai_config(user=Depends(require_api_key)):
    """Fetch AI configuration (Mask API Keys)"""
    config = await AIService.get_config()
    # 统一脱敏逻辑
    for key in ['api_key', 'embed_api_key', 'rerank_api_key']:
        if config.get(key):
            val = config[key]
            config[key] = f"{val[:4]}****{val[-4:]}" if len(val) > 8 else "********"
    return config

@router.post("/config/ai")
async def update_ai_config(payload: ConfigUpdate, user=Depends(require_permission("element:config:save"))):
    """Update AI configuration items"""
    async with get_db_connection() as db:
        async with db.cursor() as cursor:
            for key, value in payload.configs.items():
                full_key = f"ai.{key}"
                # 如果是掩码后的密钥，跳过更新
                if key in ['api_key', 'embed_api_key', 'rerank_api_key'] and '****' in str(value): 
                    continue
                
                await cursor.execute(
                    """
                    INSERT INTO sys_config (config_key, config_value, config_group) 
                    VALUES (%s, %s, 'ai') 
                    ON DUPLICATE KEY UPDATE config_value = VALUES(config_value)
                    """,
                    (full_key, str(value))
                )
    return {"message": "AI configuration updated successfully"}

@router.post("/config/ai/test")
async def test_ai_connection(payload: ConfigUpdate, user=Depends(require_permission("element:config:save"))):
    """Test AI connection"""
    try:
        config_to_test = payload.configs.copy()
        if 'api_key' in config_to_test and '****' in config_to_test['api_key']:
            real_config = await AIService.get_config()
            config_to_test['api_key'] = real_config['api_key']
        success = await AIService.test_connection(config_to_test)
        return {"success": success}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# --- 3. Diagnostics & Maintenance (Restored) ---

@router.post("/test-connection/{component}")
async def test_component_connection(component: str, user=Depends(require_api_key)):
    """Test connection to system components (Redis, Vector, etc.)"""
    # Relaxed permission for vector capability check (needed for UI adaptation)
    if component == "vector":
        pass
    else:
        # Enforce strict permission for other diagnostic tools
        # We need to manually check permission here since we removed Depends()
        # require_permission returns a dependency callable, we can't call it directly easily here without request/response context.
        # Instead, we check user permissions dict.
        # Assuming user dict structure from AuthService.verify_api_key
        # user = {"user_id": ..., "permissions": {"elements": [...]}}
        
        # Check if user is admin
        if user.get("role") == "admin":
            pass
        else:
            perms = user.get("permissions", {}).get("elements", [])
            if "element:config:save" not in perms:
                raise HTTPException(status_code=403, detail="Permission denied")

    logs = []
    status = "success"
    message = f"{component.capitalize()} check successful"
    
    try:
        if component == "vector":
            logs.append("Checking Redis Vector Support...")
            result = await VectorService.check_capability()
            
            # Add DB warning if exists
            if result.get("db_warning"):
                logs.append(result.get("db_warning"))

            if result.get("supported"):
                logs.append(result.get("message"))
                logs.append(f"Loaded Modules: {', '.join(result.get('modules', []))}")
            else:
                status = "failed"
                message = "Vector Search NOT supported"
                logs.append(result.get("message") or result.get("error"))
                logs.append(f"Loaded Modules: {', '.join(result.get('modules', []))}")
                
        elif component == "redis":
            redis = await get_redis()
            logs.append("Ping Redis...")
            await redis.ping()
            logs.append("✅ Redis PONG received")
        else:
            raise HTTPException(status_code=400, detail=f"Unknown component: {component}")
            
    except HTTPException:
        # Re-raise HTTP exceptions to maintain correct status codes
        raise
    except Exception as e:
        status = "failed"
        message = f"Check failed: {str(e)}"
        logs.append(f"❌ Error: {str(e)}")
        
    return {"status": status, "message": message, "logs": logs}

@router.post("/redis/keys")
async def scan_redis_keys(user=Depends(require_admin)):
    """Scan and list keys in Redis (for debugging)"""
    try:
        redis = await get_redis()
        if not redis:
            return {"count": 0, "keys": [], "error": "Redis is disabled"}
        keys = await redis.keys("*")
        # Since decode_responses=True is used in core/redis.py, keys are already strings
        return {"count": len(keys), "keys": keys[:50]}
    except Exception as e:
        logger.error(f"Redis scan failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/logs/maintenance")
async def get_maintenance_logs(user=Depends(require_permission("element:config:save")), limit: int = 20):
    """Fetch recent maintenance logs"""
    async with get_db_connection() as db:
        import aiomysql
        async with db.cursor(aiomysql.DictCursor) as cursor:
            await cursor.execute("SELECT * FROM sys_maintenance_log ORDER BY created_at DESC LIMIT %s", (limit,))
            return await cursor.fetchall()

@router.post("/logs/purge")
async def trigger_log_purge(request: PurgeRequest, user=Depends(require_permission("element:config:save"))):
    """Manually trigger log purge task"""
    from app.jobs.cleaner import clean_old_access_logs
    asyncio.create_task(clean_old_access_logs(retention_days=request.days, operator=user['user_name']))
    return {"message": "Cleaning task started in background"}

@router.post("/logs/aggregate")
async def trigger_aggregation(days: int = Body(7, embed=True), user=Depends(require_permission("element:config:save"))):
    """Manually trigger log aggregation task"""
    from app.jobs.aggregator import run_history_aggregation
    asyncio.create_task(run_history_aggregation(days=days, operator=user['user_name']))
    return {"message": "Aggregation task started in background"}

@router.get("/logs/shards")
async def get_log_shards_info(user=Depends(require_permission("element:config:save"))):
    """Fetch information about all log shard tables including record count and size"""
    async with get_db_connection() as db:
        import aiomysql
        async with db.cursor(aiomysql.DictCursor) as cursor:
            # 查询 information_schema 获取表统计信息
            sql = """
                SELECT 
                    TABLE_NAME as table_name,
                    TABLE_ROWS as row_count,
                    ROUND((DATA_LENGTH + INDEX_LENGTH) / 1024 / 1024, 2) as size_mb,
                    CREATE_TIME as created_at
                FROM information_schema.TABLES 
                WHERE TABLE_SCHEMA = DATABASE() 
                AND TABLE_NAME LIKE 'api_access_logs_20%%'
                ORDER BY TABLE_NAME DESC
            """
            await cursor.execute(sql)
            return await cursor.fetchall()
