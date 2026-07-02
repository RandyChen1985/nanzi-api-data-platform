from typing import Dict, Optional, Any
import asyncio
import json
import aiomysql
import inspect
from asynch.pool import Pool as AsynchPool
try:
    import oracledb
    import platform
    import os
except ImportError:
    oracledb = None
    import platform
    import os

try:
    import aioodbc
except ImportError:
    aioodbc = None
    
import logging

logger = logging.getLogger(__name__)

# Global flag to track Oracle Thick Mode initialization status
_thick_mode_initialized = False

def force_reset_oracle_mode():
    """Force reset Oracle mode state - last resort"""
    global _thick_mode_initialized
    try:
        # Try to import and reload the oracledb module to reset state
        import importlib
        import oracledb
        importlib.reload(oracledb)
        _thick_mode_initialized = False
        logger.info("Oracle module state reset")
        return True
    except Exception as e:
        logger.warning(f"Failed to reset Oracle module state: {e}")
        return False

def init_oracle_thick_mode():
    """Explicitly initialize Oracle Thick Mode"""
    global _thick_mode_initialized
    
    # Check if already initialized
    if _thick_mode_initialized:
        logger.debug("Oracle Thick Mode already initialized, skipping.")
        return True  # Return True to indicate it's ready
    
    # Check if Thick Mode is explicitly requested
    if os.environ.get("USE_ORACLE_THICK_MODE") != "1":
        logger.info("Oracle Thick Mode initialization skipped (defaulting to Thin Mode). Set USE_ORACLE_THICK_MODE=1 to enable.")
        return False

    if oracledb is None:
        logger.warning("oracledb module not found, skipping Thick Mode initialization")
        return False

    try:
        # Force thick mode initialization
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        lib_dir = None
        
        system = platform.system().lower()
        if system == "darwin":
            mac_lib = os.path.join(project_root, "libs", "oracle", "mac")
            if os.path.exists(mac_lib):
                lib_dir = mac_lib
        elif system == "linux":
            linux_lib = os.path.join(project_root, "libs", "oracle", "linux")
            docker_lib = os.path.join(project_root, "docker", "libs", "instantclient_19_30")
            
            if os.path.exists(linux_lib):
                lib_dir = linux_lib
            elif os.path.exists(docker_lib):
                lib_dir = docker_lib
            elif os.path.exists("/opt/oracle/instantclient"):
                lib_dir = "/opt/oracle/instantclient"

        # Try multiple times to initialize thick mode
        for attempt in range(3):
            try:
                if lib_dir:
                    oracledb.init_oracle_client(lib_dir=lib_dir)
                    logger.info(f"Oracle Thick Mode initialized successfully with lib_dir: {lib_dir}")
                else:
                    # If no lib_dir, but LD_LIBRARY_PATH is set, calling it without args works
                    if os.environ.get("LD_LIBRARY_PATH"):
                        oracledb.init_oracle_client()
                        logger.info("Oracle Thick Mode initialized using LD_LIBRARY_PATH")
                    else:
                        logger.warning("Oracle Instant Client not found, and LD_LIBRARY_PATH not set.")
                        return False
                
                _thick_mode_initialized = True
                return True
            except Exception as init_error:
                error_msg = str(init_error)
                if "DPY-2053" in error_msg or "already been enabled" in error_msg or "already initialized" in error_msg:
                    logger.info(f"Oracle Thick Mode already enabled (attempt {attempt + 1}): {error_msg}")
                    _thick_mode_initialized = True
                    return True
                elif attempt < 2:
                    logger.warning(f"Initialization attempt {attempt + 1} failed, retrying: {init_error}")
                    continue
                else:
                    logger.error(f"All initialization attempts failed: {init_error}")
                    return False
                    
    except Exception as e:
        logger.error(f"Unexpected error during Oracle Thick Mode initialization: {e}")
        return False

# Initial call when module is loaded
# Only initialize if thick mode is requested
if os.environ.get("USE_ORACLE_THICK_MODE") == "1":
    init_result = init_oracle_thick_mode()
    if not init_result:
        logger.warning("Failed to initialize Oracle Thick Mode during module import")

import asyncio  # Ensure asyncio is imported

class DataSourcePoolManager:
    """Singleton manager for database connection pools"""
    _pools: Dict[int, any] = {}

    @staticmethod
    def _build_oracle_dsn(datasource: Any) -> str:
        """
        Build Oracle connect descriptor via makedsn (same semantics as yovole-yunshu-ai-agent-platform).

        Default: database_name is SID. For SERVICE_NAME use either:
        - extra_params.service_name — explicit service name, or
        - extra_params.oracle_use_service_name / use_service_name — treat database_name as SERVICE_NAME.
        """
        if oracledb is None:
            raise RuntimeError("oracledb is not installed")

        host = datasource.host
        port = int(datasource.port or 1521)
        extra = datasource.extra_params
        if isinstance(extra, str):
            extra = json.loads(extra.strip()) if extra.strip() else {}
        if not isinstance(extra, dict):
            extra = {}
        extra = extra or {}

        def _json_bool(val: Any) -> bool:
            if val is True:
                return True
            if val is False or val is None:
                return False
            if isinstance(val, str):
                return val.strip().lower() in ("1", "true", "yes", "on")
            return bool(val)

        explicit_service = extra.get("service_name")
        use_db_as_service = _json_bool(extra.get("oracle_use_service_name")) or _json_bool(
            extra.get("use_service_name")
        )

        if explicit_service:
            dsn = oracledb.makedsn(host, port, service_name=str(explicit_service))
            logger.debug("Oracle DSN: SERVICE_NAME from extra_params.service_name")
            return dsn
        if use_db_as_service:
            if not datasource.database_name:
                raise ValueError(
                    "Oracle: database_name is required when oracle_use_service_name / use_service_name is set"
                )
            dsn = oracledb.makedsn(host, port, service_name=str(datasource.database_name))
            logger.debug("Oracle DSN: SERVICE_NAME from database_name (oracle_use_service_name)")
            return dsn
        if not datasource.database_name:
            raise ValueError(
                "Oracle: database_name (SID) is required, or set extra_params.service_name / oracle_use_service_name"
            )
        dsn = oracledb.makedsn(host, port, sid=str(datasource.database_name))
        logger.debug("Oracle DSN: SID from database_name (default, aligned with AI Agent platform)")
        return dsn

    @staticmethod
    def _build_sqlserver_dsn(datasource: Any) -> str:
        """构建 SQL Server ODBC 连接串（需本机安装 ODBC Driver 17/18）。"""
        if aioodbc is None:
            raise RuntimeError("aioodbc 未安装，请执行 pip install aioodbc 并安装 Microsoft ODBC Driver")

        extra = datasource.extra_params
        if isinstance(extra, str):
            extra = json.loads(extra.strip()) if extra.strip() else {}
        if not isinstance(extra, dict):
            extra = {}
        extra = extra or {}

        driver = extra.get("odbc_driver") or "ODBC Driver 18 for SQL Server"
        trust = extra.get("trust_server_certificate", True)
        # Driver 18 默认 Encrypt=yes，旧版 SQL Server 常因 TLS 不兼容报 unsupported protocol
        encrypt = extra.get("encrypt", False)
        host = datasource.host
        port = int(datasource.port or 1433)
        server = f"{host},{port}" if port else host
        database = datasource.database_name or "master"

        parts = [
            f"DRIVER={{{driver}}}",
            f"SERVER={server}",
            f"DATABASE={database}",
        ]
        if datasource.username:
            parts.append(f"UID={datasource.username}")
        if datasource.password:
            parts.append(f"PWD={datasource.password}")
        parts.append(f"Encrypt={'yes' if encrypt else 'no'}")
        if trust:
            parts.append("TrustServerCertificate=yes")
        return ";".join(parts)

    @classmethod
    async def get_pool(cls, source_id: int):
        """Get or create connection pool for a data source"""
        if source_id in cls._pools:
            logger.debug(f"Reusing existing connection pool for source_id: {source_id}")
            return cls._pools[source_id]
        
        # Fetch datasource config
        from app.services.datasource_service import DataSourceService
        datasource = await DataSourceService.get_datasource(source_id)
        
        if not datasource:
            raise ValueError(f"Data source {source_id} not found")
        
        if datasource.status != 1:
            raise ValueError(f"Data source {source_id} is inactive")
        
        # Create pool based on type
        if datasource.source_type == "clickhouse":
            pool = await cls._create_clickhouse_pool(datasource)
        elif datasource.source_type == "mysql":
            pool = await cls._create_mysql_pool(datasource)
        elif datasource.source_type == "oracle":
            pool = await cls._create_oracle_pool(datasource)
        elif datasource.source_type == "sqlserver":
            pool = await cls._create_sqlserver_pool(datasource)
        else:
            raise NotImplementedError(f"Unsupported data source type: {datasource.source_type}")
        
        cls._pools[source_id] = pool
        logger.info(f"Created connection pool for data source {source_id} ({datasource.source_name})")
        return pool
    
    @classmethod
    async def _create_oracle_pool(cls, datasource):
        """Create Oracle connection pool"""
        dsn = cls._build_oracle_dsn(datasource)
        
        # Check if we should be using thick mode
        use_thick_mode = os.environ.get("USE_ORACLE_THICK_MODE") == "1"
        
        if use_thick_mode:
            logger.info("Creating Oracle connection pool with Thick Mode (Synchronous Pool)")
            # Ensure thick mode is initialized (should be already from module load)
            if not _thick_mode_initialized:
                init_oracle_thick_mode()
                
            try:
                # IMPORTANT: Thick mode DOES NOT support create_pool_async.
                # Use synchronous version.
                pool = oracledb.create_pool(
                    user=datasource.username,
                    password=datasource.password,
                    dsn=dsn,
                    min=1,
                    max=50,
                    increment=1
                )
                logger.info("Oracle synchronous connection pool created successfully for Thick Mode")
                return pool
            except Exception as e:
                logger.error(f"Failed to create Oracle Thick Mode sync pool: {e}")
                raise
        else:
            # Thin mode - use async pool
            logger.info("Creating Oracle connection pool with Thin Mode (Asynchronous Pool)")
            pool = await oracledb.create_pool_async(
                user=datasource.username,
                password=datasource.password,
                dsn=dsn,
                min=1,
                max=50,
                increment=1
            )
            return pool
    
    @classmethod
    async def _create_clickhouse_pool(cls, datasource):
        """Create ClickHouse connection pool"""
        pool = AsynchPool(
            host=datasource.host,
            port=datasource.port,
            database=datasource.database_name or "default",
            user=datasource.username or "default",
            password=datasource.password or "",
            minsize=1,
            maxsize=100,
            encoding_errors="replace"
        )
        return pool
    
    @classmethod
    async def _create_mysql_pool(cls, datasource):
        """Create MySQL connection pool"""
        pool = await aiomysql.create_pool(
            host=datasource.host,
            port=datasource.port,
            db=datasource.database_name or "",
            user=datasource.username or "root",
            password=datasource.password or "",
            minsize=1,
            maxsize=100,
            autocommit=False
        )
        return pool

    @classmethod
    async def _create_sqlserver_pool(cls, datasource):
        """Create SQL Server connection pool (aioodbc)"""
        dsn = cls._build_sqlserver_dsn(datasource)
        pool = await aioodbc.create_pool(
            dsn=dsn,
            minsize=1,
            maxsize=50,
            autocommit=True,
        )
        return pool
    
    @classmethod
    async def invalidate_pool(cls, source_id: int):
        """Remove and close pool for a data source"""
        if source_id in cls._pools:
            pool = cls._pools.pop(source_id)
            logger.info(f"Invalidating pool for data source {source_id}")
            
            try:
                # 1. Update: Call close() (handle if it's async)
                if hasattr(pool, 'close'):
                    res = pool.close()
                    # Oracle oracledb 2.x AsyncPool.close() is a coroutine
                    if asyncio.iscoroutine(res) or inspect.isawaitable(res):
                        await res
                
                # 2. Update: Wait for closure if supported (aiomysql)
                if hasattr(pool, 'wait_closed'):
                    await pool.wait_closed()
                    
                logger.info(f"Successfully closed pool for data source {source_id}")
            except Exception as e:
                logger.error(f"Error closing pool for data source {source_id}: {e}")

    @classmethod
    async def get_pool_status(cls, source_id: int) -> dict:
        """Get status of a specific connection pool"""
        if source_id not in cls._pools:
            return {"status": "not_initialized", "active": 0, "free": 0, "max": 0}
        
        pool = cls._pools[source_id]
        status = {"status": "active"}
        
        # ClickHouse (asynch)
        if isinstance(pool, AsynchPool):
            status["max"] = pool.maxsize
            status["min"] = pool.minsize
            status["active"] = pool.size  # Current open connections
            status["free"] = pool.freesize
        
        # MySQL (aiomysql)
        elif isinstance(pool, aiomysql.Pool):
            status["max"] = pool.maxsize
            status["min"] = pool.minsize
            status["active"] = pool.size
            status["free"] = pool.freesize

        # SQL Server (aioodbc)
        elif aioodbc is not None and isinstance(pool, aioodbc.Pool):
            status["max"] = pool.maxsize
            status["min"] = pool.minsize
            status["active"] = pool.size
            status["free"] = pool.freesize
        
        # Oracle (oracledb)
        elif hasattr(pool, 'opened'): # oracledb.AsyncPool
            status["max"] = pool.max
            status["min"] = pool.min
            status["active"] = pool.opened
            status["free"] = pool.opened - pool.busy
        
        return status

    @classmethod
    async def check_health(cls) -> dict:
        """Check health of all active pools (ping test) in parallel"""
        results = {}
        
        async def check_single_pool(sid, p):
            try:
                # 1. ClickHouse
                if isinstance(p, AsynchPool):
                    async with p.acquire() as conn:
                        await conn.execute("SELECT 1")
                # 2. MySQL
                elif isinstance(p, aiomysql.Pool):
                    async with p.acquire() as conn:
                        async with conn.cursor() as cursor:
                            await cursor.execute("SELECT 1")
                # 3. SQL Server (aioodbc)
                elif aioodbc is not None and isinstance(p, aioodbc.Pool):
                    async with p.acquire() as conn:
                        async with conn.cursor() as cursor:
                            await cursor.execute("SELECT 1")
                            await cursor.fetchone()
                # 4. Oracle (AsyncPool - Thin Mode)
                elif hasattr(p, 'acquire') and asyncio.iscoroutinefunction(p.acquire):
                    conn = await p.acquire()
                    async with conn:
                        async with conn.cursor() as cursor:
                            await cursor.execute("SELECT 1 FROM DUAL")
                # 4. Oracle (Sync Pool - Thick Mode)
                elif hasattr(p, 'acquire'):
                    def sync_ping():
                        with p.acquire() as conn:
                            with conn.cursor() as cursor:
                                cursor.execute("SELECT 1 FROM DUAL")
                    await asyncio.to_thread(sync_ping)
                    
                return sid, "healthy"
            except Exception as e:
                logger.error(f"Pool {sid} health check failed: {e}")
                return sid, f"unhealthy: {str(e)}"

        # Gather all checks
        tasks = [check_single_pool(sid, pool) for sid, pool in cls._pools.items()]
        if not tasks:
            return {}
            
        check_results = await asyncio.gather(*tasks)
        for sid, status in check_results:
            results[sid] = status
            
        return results
