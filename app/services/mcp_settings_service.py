from typing import Any, Dict

from app.services.system_service import SystemService


class McpSettingsService:
    CONFIG_ENABLED = "mcp.server.enabled"
    CONFIG_INSTRUCTIONS = "mcp.server.instructions"
    SSE_PATH = "/mcp/sse"

    DEFAULT_INSTRUCTIONS = (
        "云枢数据平台 MCP：先调用 yunshu_list_resources 查看可访问资源，"
        "yunshu_search_metadata 检索表/指标元数据，yunshu_query_resource 按资源 Key 查询数据。"
    )

    @classmethod
    def normalize_base_url(cls, url: str) -> str:
        return (url or "").strip().rstrip("/")

    @classmethod
    def with_request_base(cls, settings: Dict[str, Any], request_base_url: str) -> Dict[str, Any]:
        """根据当前 HTTP 请求的访问根地址补全 public_base_url / sse_url（不入库）。"""
        base = cls.normalize_base_url(request_base_url)
        out = dict(settings)
        out["public_base_url"] = base
        out["sse_url"] = f"{base}{cls.SSE_PATH}" if base else ""
        return out

    @classmethod
    async def is_enabled(cls) -> bool:
        return await SystemService.get_bool_config(cls.CONFIG_ENABLED, False)

    @classmethod
    async def get_settings(cls, request_base_url: str = "") -> Dict[str, Any]:
        instructions = await SystemService.get_config(cls.CONFIG_INSTRUCTIONS, cls.DEFAULT_INSTRUCTIONS)
        core = {
            "enabled": await cls.is_enabled(),
            "instructions": (instructions or cls.DEFAULT_INSTRUCTIONS).strip(),
            "sse_path": cls.SSE_PATH,
            "stdio_command": "python -m yunshu_mcp",
        }
        return cls.with_request_base(core, request_base_url)

    @classmethod
    async def update_settings(
        cls,
        *,
        enabled: bool,
        instructions: str,
    ) -> None:
        await SystemService.set_config(
            cls.CONFIG_ENABLED,
            "true" if enabled else "false",
            "mcp",
        )
        await SystemService.set_config(
            cls.CONFIG_INSTRUCTIONS,
            (instructions or cls.DEFAULT_INSTRUCTIONS).strip(),
            "mcp",
        )
