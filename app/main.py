from fastapi import FastAPI, HTTPException, Cookie, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import get_swagger_ui_html, get_redoc_html
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.exceptions import RequestValidationError # Import Validation Error
from contextlib import asynccontextmanager
from typing import Optional
from app.api.v1.endpoints import query, universal, sql_execution, meta, resources
from app.api.portal.api import portal_router
from app.core.config import settings
from app.core import database, redis
from app.core.middleware import AccessLogMiddleware
from app.services.auth_service import AuthService
from app.services.meta_service import MetaService
from app.core.errors import ErrorCode
from app.core.openapi import custom_openapi, tags_metadata # Import OpenAPI Logic
from asynch.errors import InterfaceError
from aiomysql import OperationalError
from app.jobs.scheduler import start_scheduler, shutdown_scheduler
from app.mcp_integration import mount_mcp_server, wrap_mcp_gate
import logging
import datetime
import uuid

# Configure logging from settings
_log_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)
logging.basicConfig(
    level=_log_level,
    format="%(levelname)s:     %(message)s",
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    # Oracle Thick Mode is already initialized during module import in pool_manager.py
    
    await database.init_db()
    await redis.init_redis()
    start_scheduler()
    
    yield
    # Shutdown
    shutdown_scheduler()
    await database.close_db()
    await redis.close_redis()

app = FastAPI(
    title="云枢·数据服务平台",
    description="""
## 概述

云枢数据服务平台提供统一的数据查询接口，支持动环数据、智服平台资源等多源数据访问。
基于 FastAPI 构建，对接 ClickHouse (OLAP) 和 MySQL (元数据)，提供高性能、低延迟的数据服务。

## 核心特性

- 🚀 **高性能查询**：基于 ClickHouse，支持百万级数据快速检索
- 🔒 **安全认证**：API Key 加密存储，基于角色的访问控制
- 📊 **多数据源**：统一适配器模式，屏蔽底层数据库差异
- 🎯 **灵活查询**：支持通用查询和资源化接口两种模式
- 📝 **完整审计**：全量访问日志，支持导出和分析

## 认证方式

所有接口（除登录外）需要在请求头中携带 API Key：

```
X-API-Key: your_api_key_here
```

## 限流策略

- **普通用户**：100 次/分钟 (动态配置)
- **管理员**：1000 次/分钟 (动态配置)

## 响应格式

所有接口统一返回以下格式：

```json
{
  "code": 200,
  "message": "success",
  "data": { ... },
  "timestamp": "2025-01-01T12:00:00+08:00",
  "trace_id": "..."
}
```

分页查询的 `data` 结构：

```json
{
  "items": [...],
  "total": 100,
  "page": 1,
  "size": 20,
  "pages": 5
}
```

## 联系方式

- **技术支持**：cexlong@gmail.com
    """,
    version="1.0.0",
    contact={
        "name": "Yunshu API Data Platform",
        "email": "cexlong@gmail.com",
    },
    license_info={
        "name": "MIT License",
        "url": "https://opensource.org/licenses/MIT",
    },
    openapi_tags=tags_metadata,
    lifespan=lifespan,
    docs_url=None,       # Disable default Docs
    redoc_url=None,      # Disable default ReDoc
    openapi_url=None     # Disable default OpenAPI schema
)

# Global Exception Handlers for Resilience
@app.exception_handler(InterfaceError)
@app.exception_handler(OperationalError)
async def database_connection_exception_handler(request: Request, exc: Exception):
    """
    Handle Database Connection Errors.
    Return 503 Service Unavailable with specific business code.
    """
    logging.error("Database error on %s %s: %s", request.method, request.url.path, exc)
    trace_id = getattr(request.state, "trace_id", str(uuid.uuid4()))
    return JSONResponse(
        status_code=503,
        content={
            "code": ErrorCode.DATABASE_CONNECTION_FAILED,
            "message": "数据库连接失败",
            "detail": str(exc) if settings.API_SERVICE_ENV != "production" else "数据库暂时不可用，请稍后重试。",
            "data": None,
            "timestamp": datetime.datetime.now().isoformat(),
            "trace_id": trace_id
        },
        headers={"Retry-After": "30"}
    )

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """
    Standardize Request Validation Errors (400).
    Convert Pydantic validation errors to standard ErrorResponse format.
    """
    trace_id = getattr(request.state, "trace_id", str(uuid.uuid4()))
    return JSONResponse(
        status_code=400,
        content={
            "code": ErrorCode.INVALID_PARAMETER,
            "message": "参数校验失败",
            "detail": str(exc.errors()), # Or format properly as a list of errors
            "data": None,
            "timestamp": datetime.datetime.now().isoformat(),
            "trace_id": trace_id
        }
    )

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """
    Standardize HTTPException responses.
    Map status_code to business code if applicable.
    """
    trace_id = getattr(request.state, "trace_id", str(uuid.uuid4()))
    # Determine business code from status code if not already set
    code = exc.status_code
    if exc.status_code == 401: code = ErrorCode.UNAUTHORIZED
    elif exc.status_code == 403: code = ErrorCode.ACCESS_DENIED
    elif exc.status_code == 404: code = ErrorCode.RESOURCE_NOT_FOUND
    elif exc.status_code == 429: code = ErrorCode.TOO_MANY_REQUESTS
    
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "code": code,
            "message": str(exc.detail),
            "detail": exc.detail, # Include detail for consistency and testing
            "data": None,
            "timestamp": datetime.datetime.now().isoformat(),
            "trace_id": trace_id
        }
    )

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """
    Standardize all other unhandled exceptions (500).
    """
    logging.error(f"Unhandled exception: {exc}", exc_info=True)
    trace_id = getattr(request.state, "trace_id", str(uuid.uuid4()))
    return JSONResponse(
        status_code=500,
        content={
            "code": ErrorCode.INTERNAL_SERVER_ERROR,
            "message": "服务器内部错误",
            "detail": str(exc) if settings.API_SERVICE_ENV != "production" else "系统遇到未预期错误，请联系技术支持。",
            "data": None,
            "timestamp": datetime.datetime.now().isoformat(),
            "trace_id": trace_id
        }
    )

# Middleware
from app.core.middleware import TimingMiddleware
app.add_middleware(TimingMiddleware)
app.add_middleware(AccessLogMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from app.api.v1.schemas.data import COMMON_ERROR_RESPONSES
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os

# Routers
app.include_router(
    query.router, 
    prefix="/api/v1/query", 
    tags=["通用查询"],
    responses=COMMON_ERROR_RESPONSES
)
app.include_router(
    sql_execution.router,
    prefix="/api/v1/sql",
    tags=["通用查询"],
    responses=COMMON_ERROR_RESPONSES
)
app.include_router(
    universal.router,
    prefix="/api/v1", # Router defined as /resources/{key}
    responses=COMMON_ERROR_RESPONSES
)
app.include_router(
    meta.router,
    prefix="/api/v1/meta",
    tags=["元数据检索"],
    responses=COMMON_ERROR_RESPONSES
)
app.include_router(
    resources.router,
    prefix="/api/v1",
    tags=["资源发现"],
    responses=COMMON_ERROR_RESPONSES,
)
app.include_router(portal_router, prefix="/api/portal", include_in_schema=False)  # 不在文档中显示

wrap_mcp_gate(app)
mount_mcp_server(app)

@app.get("/health")
async def health_check():
    checks = {"mysql": "ok", "redis": "ok"}
    try:
        async with database.get_db_connection() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute("SELECT 1")
    except Exception as exc:
        checks["mysql"] = str(exc)

    if settings.REDIS_ENABLE:
        try:
            r = await redis.get_redis()
            if r:
                await r.ping()
            else:
                checks["redis"] = "unavailable"
        except Exception as exc:
            checks["redis"] = str(exc)
    else:
        checks["redis"] = "disabled"

    healthy = checks["mysql"] == "ok" and checks["redis"] in ("ok", "disabled")
    payload = {
        "status": "ok" if healthy else "degraded",
        "checks": checks,
        "version": app.version,
    }
    return JSONResponse(status_code=200 if healthy else 503, content=payload)

# --- Documentation Security ---

async def get_current_user_from_cookie(admin_token: Optional[str] = Cookie(None)):
    """Dependency to verify user access via Cookie for Docs (supports both admin and regular users)"""
    if not admin_token:
        # Redirect to login page if no token
        return None
    
    user = await AuthService.verify_api_key(admin_token)
    if not user:
        return None
        
    return user

@app.get("/docs", include_in_schema=False)
async def custom_swagger_ui_html(user: Optional[dict] = Depends(get_current_user_from_cookie)):
    if not user:
        return RedirectResponse("/login?next=/docs")
    return get_swagger_ui_html(
        openapi_url="/openapi.json",
        title=app.title + " - Swagger UI",
        oauth2_redirect_url=app.swagger_ui_oauth2_redirect_url,
        swagger_ui_parameters={"persistAuthorization": True}
    )

@app.get("/redoc", include_in_schema=False)
async def redoc_html(user: Optional[dict] = Depends(get_current_user_from_cookie)):
    if not user:
        return RedirectResponse("/login?next=/redoc")
    return get_redoc_html(
        openapi_url="/openapi.json",
        title=app.title + " - ReDoc"
    )

@app.get("/openapi.json", include_in_schema=False)
async def get_open_api_endpoint(user: Optional[dict] = Depends(get_current_user_from_cookie)):
    if not user:
         # For JSON endpoint, returning 401/403 is better than redirect usually, 
         # but to force browser login flow, redirect is okay or let Swagger UI handle it.
         # Actually Swagger UI calls this via AJAX. Redirect might fail CORS or opaque.
         # Let's return 401 if unauthorized for JSON.
         raise HTTPException(status_code=401, detail="Unauthorized")
    return await custom_openapi(app)

# Mount frontend static assets if they exist
frontend_dist = "frontend/dist"
assets_path = os.path.join(frontend_dist, "assets")

if os.path.exists(assets_path):
    app.mount("/assets", StaticFiles(directory=assets_path), name="assets")

@app.get("/{full_path:path}")
async def serve_spa(full_path: str):
    # Skip API routes (handled above)
    if full_path.startswith("api") or full_path.startswith("mcp"):
         raise HTTPException(status_code=404, detail="API Not Found")

    # Check if file exists in frontend_dist (for favicon.ico, favicon.png, etc.)
    file_path = os.path.join(frontend_dist, full_path)
    if os.path.exists(file_path) and os.path.isfile(file_path):
        return FileResponse(file_path)

    # Serve index.html for all other routes (SPA)
    index_file = os.path.join(frontend_dist, "index.html")
    if os.path.exists(index_file):
        response = FileResponse(index_file)
        # 强制禁用 index.html 缓存，确保前端更新能立即生效
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        return response
    
    return {"message": "Admin Portal is being built. Please run `cd frontend && npm run build`."}
