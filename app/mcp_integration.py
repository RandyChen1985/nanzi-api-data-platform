import logging

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from app.services.mcp_settings_service import McpSettingsService
from yunshu_mcp.auth_context import (
    reset_mcp_api_key,
    resolve_api_key_for_scope,
    set_mcp_api_key,
)

logger = logging.getLogger(__name__)

MCP_MOUNT_PATH = "/mcp"
_mcp_sse_mounted = False


def is_mcp_sse_mounted() -> bool:
    """当前进程是否已成功挂载 MCP SSE 子应用（勿对 /mcp/sse 发普通 HTTP 探测）。"""
    return _mcp_sse_mounted


class McpEnabledMiddleware:
    """MCP 未启用时拒绝 /mcp 路径；SSE 请求从 X-API-Key 注入调用方凭证。"""

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http":
            path = scope.get("path", "")
            if path.startswith(MCP_MOUNT_PATH):
                if not await McpSettingsService.is_enabled():
                    response = JSONResponse(
                        status_code=503,
                        content={
                            "code": 503,
                            "message": "MCP Server 未启用",
                            "detail": "请在管理后台「系统配置 → MCP 服务」中开启",
                        },
                    )
                    await response(scope, receive, send)
                    return

                api_key = resolve_api_key_for_scope(scope)
                token = set_mcp_api_key(api_key or None)
                try:
                    await self.app(scope, receive, send)
                finally:
                    reset_mcp_api_key(token)
                return
        await self.app(scope, receive, send)


def mount_mcp_server(app: FastAPI) -> None:
    """将 MCP SSE 应用挂载到 FastAPI（/mcp/sse）。"""
    global _mcp_sse_mounted
    try:
        from yunshu_mcp.server import get_mcp_server

        mcp = get_mcp_server()
        sse_app = mcp.sse_app()
        app.mount(MCP_MOUNT_PATH, sse_app)
        _mcp_sse_mounted = True
        logger.info("MCP SSE mounted at %s/sse", MCP_MOUNT_PATH)
    except Exception as exc:
        _mcp_sse_mounted = False
        logger.warning("Failed to mount MCP SSE app: %s", exc)


def wrap_mcp_gate(app: FastAPI) -> None:
    """为整个应用套上 MCP 开关中间件。"""
    app.add_middleware(McpEnabledMiddleware)
