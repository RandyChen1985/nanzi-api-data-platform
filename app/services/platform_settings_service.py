from typing import Any, Dict, Optional

from app.schemas.platform_settings import (
    CatalogPlatformSettings,
    DingTalkPlatformSettings,
    McpPlatformSettings,
    PlatformSettingsResponse,
    PlatformSettingsUpdate,
)
from app.services.catalog_service import CatalogService
from app.services.dingtalk_notification_service import DingTalkNotificationService
from app.services.mcp_settings_service import McpSettingsService


class PlatformSettingsService:
    @classmethod
    async def get_settings(cls, request_base_url: str = "") -> PlatformSettingsResponse:
        catalog_raw = await CatalogService.get_catalog_settings()
        dingtalk_raw = await DingTalkNotificationService.get_settings()
        mcp_raw = await McpSettingsService.get_settings(request_base_url)
        return PlatformSettingsResponse(
            catalog=CatalogPlatformSettings(**catalog_raw),
            dingtalk=DingTalkPlatformSettings(**dingtalk_raw),
            mcp=McpPlatformSettings(**mcp_raw),
        )

    @classmethod
    async def update_settings(
        cls,
        body: PlatformSettingsUpdate,
        *,
        request_base_url: str = "",
    ) -> PlatformSettingsResponse:
        if body.catalog is not None:
            await CatalogService.update_catalog_settings(
                default_owner_strategy=body.catalog.default_owner_strategy,
                group_owner_map=body.catalog.group_owner_map,
                notify_resource_change_enabled=body.catalog.notify_resource_change_enabled,
                notify_resource_change_webhook_url=body.catalog.notify_resource_change_webhook_url,
            )
        if body.dingtalk is not None:
            await DingTalkNotificationService.update_settings(
                enabled=body.dingtalk.enabled,
                webhook_url=body.dingtalk.webhook_url,
                secret=body.dingtalk.secret,
                notify_on_request=body.dingtalk.notify_on_request,
                notify_on_result=body.dingtalk.notify_on_result,
            )
        if body.mcp is not None:
            await McpSettingsService.update_settings(
                enabled=body.mcp.enabled,
                instructions=body.mcp.instructions,
            )
        return await cls.get_settings(request_base_url)

    @classmethod
    async def get_catalog_dict(cls) -> Dict[str, Any]:
        return (await cls.get_settings()).catalog.model_dump()
