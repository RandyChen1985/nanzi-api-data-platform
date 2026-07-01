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


class PlatformSettingsResponse(BaseModel):
    catalog: CatalogPlatformSettings
    dingtalk: DingTalkPlatformSettings


class PlatformSettingsUpdate(BaseModel):
    catalog: Optional[CatalogPlatformSettings] = None
    dingtalk: Optional[DingTalkPlatformSettings] = None
