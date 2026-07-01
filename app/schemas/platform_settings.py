from typing import Dict, Optional

from pydantic import BaseModel, Field


class CatalogPlatformSettings(BaseModel):
    default_owner_strategy: str = "publisher"
    group_owner_map: Dict[str, int] = Field(default_factory=dict)
    notify_resource_change_enabled: bool = True
    notify_resource_change_webhook_url: str = ""


class DingTalkPlatformSettings(BaseModel):
    enabled: bool = False
    webhook_url: str = ""
    secret: str = ""
    notify_on_request: bool = True
    notify_on_result: bool = True


class McpPlatformSettings(BaseModel):
    enabled: bool = False
    instructions: str = ""
    public_base_url: str = ""
    sse_path: str = "/mcp/sse"
    sse_url: str = ""
    stdio_command: str = "python -m yunshu_mcp"


class McpPlatformSettingsUpdate(BaseModel):
    enabled: bool = False
    instructions: str = ""


class McpTestCheck(BaseModel):
    name: str
    ok: bool
    detail: str


class McpTestResponse(BaseModel):
    success: bool
    checks: list[McpTestCheck]
    tools: list[str] = Field(default_factory=list)
    sse_url: str = ""


class PlatformSettingsResponse(BaseModel):
    catalog: CatalogPlatformSettings
    dingtalk: DingTalkPlatformSettings
    mcp: McpPlatformSettings


class PlatformSettingsUpdate(BaseModel):
    catalog: Optional[CatalogPlatformSettings] = None
    dingtalk: Optional[DingTalkPlatformSettings] = None
    mcp: Optional[McpPlatformSettingsUpdate] = None
