from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

import httpx

from app.mcp_integration import is_mcp_sse_mounted
from app.services.mcp_settings_service import McpSettingsService

EXPECTED_TOOLS = (
    "yunshu_list_resources",
    "yunshu_query_resource",
    "yunshu_search_metadata",
)


class McpTestService:
    @classmethod
    async def run_test(
        cls,
        override: Optional[Dict[str, Any]] = None,
        *,
        local_base_url: str = "",
    ) -> Tuple[bool, Dict[str, Any]]:
        checks: List[Dict[str, Any]] = []
        tools: List[str] = []

        if override is not None:
            enabled = bool(override.get("enabled"))
        else:
            settings = await McpSettingsService.get_settings()
            enabled = settings["enabled"]

        local_base = local_base_url.strip().rstrip("/")
        sse_url = f"{local_base}/mcp/sse" if local_base else ""

        checks.append(
            {
                "name": "服务开关",
                "ok": enabled,
                "detail": "已启用" if enabled else "请先开启 MCP Server 开关",
            }
        )
        if not enabled:
            return False, cls._result(checks, tools, sse_url)

        try:
            from yunshu_mcp.server import get_mcp_server

            mcp = get_mcp_server()
            registered = await mcp.list_tools()
            tools = [t.name for t in registered]
            missing = [name for name in EXPECTED_TOOLS if name not in tools]
            checks.append(
                {
                    "name": "MCP SDK",
                    "ok": not missing,
                    "detail": (
                        f"已注册 {len(tools)} 个工具：{', '.join(tools)}"
                        if not missing
                        else f"缺少工具：{', '.join(missing)}"
                    ),
                }
            )
        except Exception as exc:
            checks.append({"name": "MCP SDK", "ok": False, "detail": str(exc)})
            return False, cls._result(checks, tools, sse_url)

        db_settings = await McpSettingsService.get_settings()
        preview_mode = override is not None and enabled and not db_settings["enabled"]
        if preview_mode:
            checks.append(
                {
                    "name": "系统配置",
                    "ok": True,
                    "detail": "使用当前表单值测试（尚未保存，保存后正式生效）",
                }
            )
        else:
            checks.append(
                {
                    "name": "系统配置",
                    "ok": db_settings["enabled"] == enabled,
                    "detail": (
                        "数据库配置已加载"
                        if db_settings["enabled"] == enabled
                        else "数据库中 MCP 仍为关闭，请先保存"
                    ),
                }
            )

        probe_base = local_base
        if probe_base:
            checks.append(
                {
                    "name": "服务地址",
                    "ok": True,
                    "detail": f"{probe_base}（由当前请求自动识别）",
                }
            )
        else:
            checks.append(
                {
                    "name": "服务地址",
                    "ok": True,
                    "detail": "未识别到访问地址，已跳过 HTTP 探测",
                }
            )

        if probe_base:
            if preview_mode:
                checks.append(
                    {
                        "name": "HTTP 探测",
                        "ok": True,
                        "detail": "配置尚未保存，跳过状态探针与 SSE 检测（保存后可再次测试）",
                    }
                )
            else:
                in_process = True
                await cls._append_http_checks(checks, probe_base, in_process=in_process)

        success = all(item["ok"] for item in checks)
        return success, cls._result(checks, tools, sse_url or (f"{probe_base}/mcp/sse" if probe_base else ""))

    @classmethod
    async def _append_http_checks(
        cls,
        checks: List[Dict[str, Any]],
        base_url: str,
        *,
        in_process: bool = False,
    ) -> None:
        base = base_url.rstrip("/")
        status_body: Dict[str, Any] = {}
        status_ok = False

        try:
            async with httpx.AsyncClient(timeout=12.0, follow_redirects=True) as client:
                status_resp = await client.get(f"{base}/api/v1/mcp/status")
                try:
                    status_body = status_resp.json()
                except Exception:
                    pass
                status_ok = status_resp.status_code == 200 and status_body.get("enabled") is True
                checks.append(
                    {
                        "name": "状态探针",
                        "ok": status_ok,
                        "detail": (
                            f"GET /api/v1/mcp/status → HTTP {status_resp.status_code}，MCP 已启用"
                            if status_ok
                            else f"GET /api/v1/mcp/status → HTTP {status_resp.status_code}"
                            + (f"，{status_body.get('message', '')}" if status_body.get("message") else "")
                        ),
                    }
                )
        except Exception as exc:
            checks.append(
                {
                    "name": "状态探针",
                    "ok": False,
                    "detail": str(exc) or "无法连接状态探针",
                }
            )

        if in_process:
            mounted = is_mcp_sse_mounted()
            checks.append(
                {
                    "name": "SSE 端点",
                    "ok": mounted and status_ok,
                    "detail": (
                        "当前服务已挂载 /mcp/sse（SSE 为长连接，不在后台发 HTTP 探测）"
                        if mounted
                        else "当前进程未挂载 MCP SSE，请查看服务启动日志"
                    ),
                }
            )
        else:
            sse_url = (status_body.get("sse_url") or f"{base}/mcp/sse") if status_ok else ""
            checks.append(
                {
                    "name": "SSE 端点",
                    "ok": status_ok and bool(sse_url),
                    "detail": (
                        f"已配置 {sse_url}（远程地址仅校验状态探针，SSE 长连接请用 Cursor 实测）"
                        if status_ok and sse_url
                        else "状态探针未通过，无法确认 SSE 地址"
                    ),
                }
            )

    @staticmethod
    def _result(
        checks: List[Dict[str, Any]],
        tools: List[str],
        sse_url: str,
    ) -> Dict[str, Any]:
        return {
            "success": all(item["ok"] for item in checks),
            "checks": checks,
            "tools": tools,
            "sse_url": sse_url,
        }
