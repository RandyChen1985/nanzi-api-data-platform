import hashlib
import secrets
import httpx
import json
from typing import Optional, Dict
from app.core.database import get_db_connection
from app.core.redis import get_redis
from app.core.config import settings
from app.utils.encryption import get_api_key_manager
from passlib.context import CryptContext
import logging

logger = logging.getLogger(__name__)

# Explicitly use bcrypt and handle potential compatibility issues with newer bcrypt versions
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

class AuthService:
    @staticmethod
    async def generate_api_key(user_name: str, role: str = "user", remark: str = None, rate_limit: int = None) -> str:
        """
        生成 API 密钥（使用新的加密机制）
        
        Args:
            user_name: 用户名
            role: 角色（admin/user）
            remark: 备注
            rate_limit: 限流值
        
        Returns:
            str: 原始 API Key（明文，仅此一次返回）
        """
        # 使用加密管理器生成 API Key
        manager = get_api_key_manager()
        api_key, encrypted_key, hashed_key = manager.generate_api_key()
      
        # 插入到数据库（存储加密和哈希）
        async with get_db_connection() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(
                    """INSERT INTO api_users 
                       (user_name, api_key_encrypted, api_key_hash, role, remark, status, rate_limit) 
                       VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                    (user_name, encrypted_key, hashed_key, role, remark, 1, rate_limit)
                )
      
        return api_key

    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """Verify a password against a hash. Truncate if longer than 72 bytes due to bcrypt limitation."""
        # bcrypt has a 72-byte password length limit
        if len(plain_password.encode('utf-8')) > 72:
            # Truncate to 72 bytes while preserving UTF-8 characters properly
            password_bytes = plain_password.encode('utf-8')
            plain_password = password_bytes[:72].decode('utf-8', errors='ignore')
        return pwd_context.verify(plain_password, hashed_password)

    @staticmethod
    def get_password_hash(password: str) -> str:
        """Hash a password. Truncate if longer than 72 bytes due to bcrypt limitation."""
        # bcrypt has a 72-byte password length limit
        if len(password.encode('utf-8')) > 72:
            # Truncate to 72 bytes while preserving UTF-8 characters properly
            password_bytes = password.encode('utf-8')
            password = password_bytes[:72].decode('utf-8', errors='ignore')
        return pwd_context.hash(password)

    @staticmethod
    async def change_password(user_id: str, new_password: str, old_password: Optional[str] = None) -> bool:
        """
        Modify user password with smart validation:
        - If old password exists in DB, require and verify old_password.
        - If no password exists (first time), allow direct setting.
        """
        async with get_db_connection() as conn:
            async with conn.cursor() as cursor:
                # 1. Check existing password status
                await cursor.execute("SELECT password_hash FROM api_users WHERE id = %s", (user_id,))
                result = await cursor.fetchone()
                
                if result and result[0]:
                    # Password exists, MUST verify old one
                    if not old_password:
                        raise ValueError("需要提供旧密码以验证身份")
                    if not AuthService.verify_password(old_password, result[0]):
                        raise ValueError("旧密码验证失败")

                # 2. Update to new password
                password_hash = AuthService.get_password_hash(new_password)
                await cursor.execute(
                    "UPDATE api_users SET password_hash = %s WHERE id = %s",
                    (password_hash, user_id)
                )
                await conn.commit()
                
                # 3. Invalidate permission cache
                from app.services.permission_service import PermissionService
                await PermissionService.invalidate_user_cache(int(user_id))
                
                return cursor.rowcount > 0

    @staticmethod
    async def authenticate_user(username: str, password: str) -> Optional[Dict]:
        """
        Authenticate a user by username and password.
        """
        async with get_db_connection() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(
                    "SELECT id, user_name, password_hash, role, status FROM api_users WHERE user_name = %s",
                    (username,)
                )
                result = await cursor.fetchone()
                
                if not result:
                    return None
                    
                user_id, db_username, db_password_hash, role, status = result
                
                if status != 1:
                    return None
                
                # Verify password
                if not db_password_hash or not AuthService.verify_password(password, db_password_hash):
                    return None
                    
                return {
                    "user_id": str(user_id),
                    "user_name": db_username,
                    "role": role
                }

    @staticmethod
    async def verify_api_key(api_key: str) -> Optional[Dict]:
        """
        校验 API Key（Redis Cache -> MySQL）
        
        Args:
            api_key: 用户提供的 API Key（明文）
        
        Returns:
            Optional[Dict]: 用户信息或 None
        """
        # 计算哈希值用于查询
        manager = get_api_key_manager()
        hashed_key = manager.hash_api_key(api_key)
        cache_key = f"auth:api_key:{hashed_key}"
        
        # 1. 尝试从 Redis 缓存获取
        redis = await get_redis()
        if redis:
            cached_user = await redis.hgetall(cache_key)
            if cached_user:
                 # 刷新过期时间，保持 Session 活跃
                 await redis.expire(cache_key, 3600)
                 return cached_user

        # 2. 从 MySQL 查询（使用哈希值）
        user_data = None
        async with get_db_connection() as conn:
            async with conn.cursor() as cursor:
                # 联表查询获取用户自己的限流值和角色定义的限流值
                # 使用 COLLATE 确保字符集匹配
                sql = """
                    SELECT 
                        u.id, u.user_name, u.role, u.status, u.created_at, u.remark,
                        u.rate_limit as user_limit,
                        r.rate_limit as role_limit,
                        u.masking_strategy as user_masking_strategy,
                        r.masking_strategy as role_masking_strategy
                    FROM api_users u
                    LEFT JOIN sys_roles r ON u.role COLLATE utf8mb4_unicode_ci = r.role_code COLLATE utf8mb4_unicode_ci
                    WHERE u.api_key_hash = %s
                """
                await cursor.execute(sql, (hashed_key,))
                result = await cursor.fetchone()
                if result and result[3] == 1:  # status == 1
                     user_data = {
                         "user_id": str(result[0]),
                         "user_name": result[1],
                         "role": result[2],
                         "created_at": result[4].strftime("%Y-%m-%d %H:%M:%S") if result[4] else None,
                         "remark": result[5] or "",
                         "user_rate_limit": result[6],
                         "role_rate_limit": result[7],
                         "masking_strategy": result[8],
                         "role_masking_strategy": result[9]
                     }
        
        # 3. 缓存到 Redis
        if user_data and redis:
            # 过滤掉 None 值，Redis 不接受 NoneType
            redis_data = {k: str(v) for k, v in user_data.items() if v is not None}
            await redis.hset(cache_key, mapping=redis_data)
            await redis.expire(cache_key, 3600)  # 1 hour cache

        return user_data

    @staticmethod
    async def reset_api_key(user_id: int) -> Optional[str]:
        """
        重置用户的 API Key
        
        Args:
            user_id: 用户 ID
        
        Returns:
            Optional[str]: 新的 API Key 或 None
        """
        # 1. 获取旧的 API Key 哈希以便清理缓存
        old_hash = None
        async with get_db_connection() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute("SELECT api_key_hash FROM api_users WHERE id = %s", (user_id,))
                row = await cursor.fetchone()
                if row:
                    old_hash = row[0]

        # 2. 生成新的 API Key
        manager = get_api_key_manager()
        api_key, encrypted_key, hashed_key = manager.generate_api_key()
        
        # 3. 更新数据库中的加密和哈希值
        async with get_db_connection() as conn:
            async with conn.cursor() as cursor:
                # 更新 API Key 的加密和哈希值
                await cursor.execute(
                    "UPDATE api_users SET api_key_encrypted = %s, api_key_hash = %s WHERE id = %s",
                    (encrypted_key, hashed_key, user_id)
                )
                
                # 如果更新成功
                if cursor.rowcount > 0:
                    redis = await get_redis()
                    if redis:
                        # 清除旧 Key 的缓存
                        if old_hash:
                            await redis.delete(f"auth:api_key:{old_hash}")
                        # 清除新 Key 的缓存（以防万一）
                        await redis.delete(f"auth:api_key:{hashed_key}")
                    
                    # 同时失效用户权限缓存
                    from app.services.permission_service import PermissionService
                    await PermissionService.invalidate_user_cache(user_id)
                    
                    return api_key
                else:
                    return None
    
    @staticmethod
    async def get_decrypted_api_key(user_id: int) -> Optional[str]:
        """
        获取用户的解密 API Key（用于查看功能）
        
        Args:
            user_id: 用户 ID
        
        Returns:
            Optional[str]: 解密后的 API Key 或 None
        """
        async with get_db_connection() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(
                    "SELECT api_key_encrypted FROM api_users WHERE id = %s AND status = 1",
                    (user_id,)
                )
                result = await cursor.fetchone()
                
                if not result or not result[0]:
                    return None
                
                # 解密 API Key
                manager = get_api_key_manager()
                try:
                    return manager.decrypt_api_key(result[0])
                except ValueError as e:
                    # 解密失败（可能密钥损坏）
                    logger.warning("Failed to decrypt API Key for user %s: %s", user_id, e)
                    return None
    
    @staticmethod
    async def verify_admin_login(api_key: str) -> Optional[Dict]:
        """校验管理员登录 (Key + Role Check)"""
        user = await AuthService.verify_api_key(api_key)
        
        if not user:
            return None
            
        # Verify role is admin
        if user.get("role") != "admin":
            return None
            
        return user

    @staticmethod
    async def expire_api_key(api_key: str):
        """
        从 Redis 中清除 API Key 缓存 (退出登录)
        """
        manager = get_api_key_manager()
        hashed_key = manager.hash_api_key(api_key)
        cache_key = f"auth:api_key:{hashed_key}"
        
        redis = await get_redis()
        if redis:
            await redis.delete(cache_key)

    @staticmethod
    async def authenticate_sso_user(username: str, password: str) -> Optional[Dict]:
        """
        通过 SSO 认证用户
        
        Args:
            username: 用户名
            password: 密码
        
        Returns:
            Optional[Dict]: 用户信息或 None
        """
        # 1. 调用 Yovole SSO API 进行认证
        sso_authenticated = False
        try:
            api_request = {
                'requestSystem': settings.SSO_REQUEST_SYSTEM,
                'requestBusiness': settings.SSO_REQUEST_BUSINESS,
                'operationType': 'LOGIN',
                'userName': username,
                'password': password
            }

            headers = {
                'YOVOLE-LAPLACE-API-ACCESS-TOKEN': settings.SSO_ACCESS_TOKEN,
                'Content-Type': 'application/json;charset=UTF-8'
            }

            async with httpx.AsyncClient(timeout=settings.SSO_TIMEOUT, verify=False) as client:
                response = await client.post(
                    settings.SSO_API_URL,
                    headers=headers,
                    json=api_request
                )
                
                if response.status_code == 200:
                    response_data = response.json()
                    if response_data.get('data'):
                        sso_authenticated = True
                    
        except httpx.TimeoutException:
            # SSO API 超时
            return None
        except Exception as e:
            # SSO API 调用失败
            logger.warning("SSO API call failed: %s", e)
            return None
        
        # 2. SSO 验证成功，查询本地用户
        if sso_authenticated:
            async with get_db_connection() as conn:
                async with conn.cursor() as cursor:
                    sql = """
                        SELECT 
                            u.id, u.user_name, u.role, u.status, u.created_at, u.remark,
                            u.rate_limit as user_limit,
                            r.rate_limit as role_limit,
                            u.masking_strategy as user_masking_strategy,
                            r.masking_strategy as role_masking_strategy
                        FROM api_users u
                        LEFT JOIN sys_roles r ON u.role COLLATE utf8mb4_unicode_ci = r.role_code COLLATE utf8mb4_unicode_ci
                        WHERE u.user_name = %s
                    """
                    await cursor.execute(sql, (username,))
                    result = await cursor.fetchone()
                    
                    if not result:
                        # 用户不存在 - SSO认证通过但本地数据库不存在
                        return {"error": "user_not_found"}
                        
                    user_id, db_username, role, status, created_at, remark, user_limit, role_limit, user_masking, role_masking = result
                    
                    if status != 1:
                        # 用户被禁用
                        return {"error": "user_disabled"}
                    
                    user_data = {
                        "user_id": str(user_id),
                        "user_name": db_username,
                        "role": role,
                        "created_at": created_at.strftime("%Y-%m-%d %H:%M:%S") if created_at else None,
                        "remark": remark or "",
                        "user_rate_limit": user_limit,
                        "role_rate_limit": role_limit,
                        "masking_strategy": user_masking,
                        "role_masking_strategy": role_masking
                    }

                    # 3. 缓存到 Redis (SSO 路径也需要缓存以提高后续权限校验性能)
                    redis = await get_redis()
                    if redis:
                        # 找到 API Key 哈希以建立关联 (这里可能需要更复杂的逻辑，
                        # 但为了简单，我们至少可以缓存按用户名查找的结果或跳过，
                        # 主要是 verify_api_key 需要缓存)
                        # 暂时只返回数据，verify_api_key 会在下一次请求时自动建立缓存
                        pass

                    return user_data
        
        # SSO 认证失败
        return None
