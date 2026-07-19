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


class WeComPlatformSettings(BaseModel):
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
    stdio_command: str = "python -m nanzi_mcp"


class BrandingPlatformSettings(BaseModel):
    enabled: bool = False
    product_name: str = "NanZi · 数据服务平台"
    login_subtitle: str = "NanZi API Data Platform"
    icon_url: str = "/favicon.png"
    hide_login_sso: bool = False
    hide_version_link: bool = False
    contact_markdown: str = ""
    copyright_text: str = ""


class BrandingPlatformSettingsUpdate(BaseModel):
    enabled: bool = False
    product_name: str = "NanZi · 数据服务平台"
    login_subtitle: str = "NanZi API Data Platform"
    icon_url: str = "/favicon.png"
    hide_login_sso: bool = False
    hide_version_link: bool = False
    contact_markdown: str = ""
    copyright_text: str = ""


class PublicBrandingResponse(BaseModel):
    enabled: bool = False
    product_name: str
    login_subtitle: str
    icon_url: str
    hide_login_sso: bool = False
    hide_version_link: bool = False
    contact_markdown: str = ""
    copyright_text: str = ""


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
    wecom: WeComPlatformSettings
    mcp: McpPlatformSettings
    branding: BrandingPlatformSettings


class PlatformSettingsUpdate(BaseModel):
    catalog: Optional[CatalogPlatformSettings] = None
    dingtalk: Optional[DingTalkPlatformSettings] = None
    wecom: Optional[WeComPlatformSettings] = None
    mcp: Optional[McpPlatformSettingsUpdate] = None
    branding: Optional[BrandingPlatformSettingsUpdate] = None
