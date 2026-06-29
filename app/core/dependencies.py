from fastapi import Header, HTTPException, status, Depends, Cookie, Request
from typing import Optional, Dict
import datetime
import logging
from app.core import redis
from app.services.auth_service import AuthService
from app.services.system_service import SystemService

logger = logging.getLogger(__name__)

async def require_api_key(
    request: Request,
    api_key_header: Optional[str] = Header(None, alias="X-API-Key"),
    authorization: Optional[str] = Header(None),
    admin_token: Optional[str] = Cookie(None)
):
    """
    Dependency to require an API Key or Token for access.
    Supports:
    1. X-API-Key Header (Highest priority)
    2. Authorization: Bearer <token> Header
    3. admin_token Cookie (For Admin Portal secure sessions)
    """
    # Priority 1 & 2: Headers (X-API-Key or Authorization)
    token_candidates = []
    
    if api_key_header:
        token_candidates.append(api_key_header)
    
    if authorization:
        if " " in authorization:
            token_candidates.append(authorization.split(" ")[1])
        else:
            token_candidates.append(authorization)
            
    # Priority 3: Cookie
    if admin_token:
        token_candidates.append(admin_token)
        
    if not token_candidates:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing API Key or Token")

    # Iterate through candidates until one works
    for token in token_candidates:
        # Quick skip for obviously masked keys to save DB hits
        if "..." in token or "***" in token:
            continue
            
        user_info = await AuthService.verify_api_key(token)
        if user_info:
            # --- FIX: Populate permissions for require_permission factory ---
            try:
                from app.services.permission_service import PermissionService
                perms_resp = await PermissionService.get_user_permissions(int(user_info["user_id"]))
                # Convert to dict and add role for legacy compatibility (e.g. is_admin check in audit.py)
                perms_dict = perms_resp.permissions.model_dump()
                perms_dict["role"] = perms_resp.role
                user_info["permissions"] = perms_dict
                user_info["role"] = perms_resp.role  # Ensure root role is also updated
            except Exception as e:
                logger.error("Error fetching permissions for user %s: %s", user_info.get("user_id"), e)
                user_info["permissions"] = {"menus": [], "elements": [], "resources": [], "role": user_info.get("role")}
            # ----------------------------------------------------------------
            request.state.user = user_info
            return user_info

    # If all candidates failed
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API Key or Token")

async def check_rate_limit(request: Request, user: Dict = Depends(require_api_key)):
    """
    Advanced rate limiting with hierarchical overrides and Fail-Open support.
    Logic: User Level -> Role Level -> Global System Level
    """
    # 1. Check Global Switch
    if not await SystemService.get_bool_config("ratelimit.enabled", True):
        return

    user_id = user.get("user_id")
    role = user.get("role", "user")

    # 2. Determine Limit (Priority: User -> Role -> Global)
    limit = None
    
    # a. User Specific Limit (from AuthService enriched user dict)
    user_limit = user.get("user_rate_limit")
    if user_limit is not None:
        limit = int(user_limit)
    
    # b. Role Specific Limit
    if limit is None:
        role_limit = user.get("role_rate_limit")
        if role_limit is not None:
            limit = int(role_limit)
            
    # c. Global Default based on role
    if limit is None:
        config_key = f"ratelimit.{role}.limit"
        limit = await SystemService.get_int_config(config_key, 100 if role == "user" else 1000)

    # 3. Redis Logic with Fail-Open
    r = await redis.get_redis()
    if not r:
        return # Fail-open: proceed if redis is down

    now = datetime.datetime.now()
    minute_key = now.strftime("%Y%m%d%H%M")
    key = f"ratelimit:v1:{user_id}:{minute_key}"
    
    try:
        # Atomic Increment
        current = await r.incr(key)
        
        if current == 1:
            await r.expire(key, 60)
        
        remaining = max(0, limit - current)
        reset_seconds = 60 - now.second

        # Prepare Headers (to be injected by caller or via Response object)
        # Store in request.state for middleware/endpoint to pickup
        request.state.ratelimit_headers = {
            "X-RateLimit-Limit": str(limit),
            "X-RateLimit-Remaining": str(remaining),
            "X-RateLimit-Reset": str(reset_seconds)
        }

        if current > limit:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded. Please try again later.",
                headers=request.state.ratelimit_headers
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.warning("Rate limit Redis error (fail-open): %s", e)
        return

async def require_admin(user: Dict = Depends(require_api_key)) -> Dict:
    """
    Dependency to ensure the current user is an admin.
    Raises 403 if user is not admin.
    """
    if user.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return user

async def verify_resource_access(user: Dict, resource_key: str):
    """
    Check if the user has permission to access the specific resource.
    Supports: Direct User Permissions + Role Inherited Permissions.
    """
    is_admin = user.get("role") == "admin"
    user_id = user.get("user_id")
    
    from app.core.database import get_db_connection
    async with get_db_connection() as conn:
        async with conn.cursor() as cursor:
            # 1. Check Resource Status
            await cursor.execute("SELECT status FROM sys_resource_meta WHERE resource_key = %s", (resource_key,))
            row = await cursor.fetchone()
            if not row:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Unknown resource: {resource_key}")
            if row[0] == 0:
                raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=f"Resource '{resource_key}' is disabled")

            # 2. Admin bypass
            if is_admin:
                return

            # 3. Check Direct Permission (sys_user_resources)
            await cursor.execute(
                "SELECT 1 FROM sys_user_resources WHERE user_id = %s AND resource_key = %s", 
                (user_id, resource_key)
            )
            if await cursor.fetchone():
                return

            # 4. Check Role Inherited Permission (New Logic)
            # Find all role_ids for this user
            await cursor.execute("SELECT role_id FROM sys_user_role_relation WHERE user_id = %s", (user_id,))
            role_rows = await cursor.fetchall()
            role_ids = [r[0] for r in role_rows]
            
            if role_ids:
                placeholders = ', '.join(['%s'] * len(role_ids))
                # Check sys_ui_permissions where perm_type='resource'
                await cursor.execute(
                    f"SELECT 1 FROM sys_ui_permissions WHERE enabled = 1 AND perm_type = 'resource' AND perm_code = %s AND role_id IN ({placeholders})",
                    (resource_key, *role_ids)
                )
                if await cursor.fetchone():
                    return

            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied: You do not have permission to access resource '{resource_key}'"
            )


def check_resource_permission(resource: str):
    """
    Dependency factory for resource permission check.
    Usage: Depends(check_resource_permission("donghuan_real_metrics"))
    """
    async def dependency(user: Dict = Depends(require_api_key)):
        await verify_resource_access(user, resource)
        return user
    return dependency

def require_permission(perm_code: str):
    """
    Factory for granular permission check dependency (Elements).
    Usage: Depends(require_permission("element:lab:generate"))
    """
    async def dependency(user: Dict = Depends(require_api_key)):
        # 1. Admin bypass
        if user.get("role") == "admin":
            return user
            
        # 2. Check Permissions (Elements)
        perms = user.get("permissions", {})
        
        # Handle if permissions is Pydantic model or dict (just in case)
        elements = []
        if isinstance(perms, dict):
             elements = perms.get("elements", [])
        else:
             elements = getattr(perms, "elements", [])

        if perm_code in elements:
            return user

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Permission denied: Required '{perm_code}'"
        )
    return dependency
