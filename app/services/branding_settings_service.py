from typing import Any, Dict

from app.services.system_service import SystemService

DEFAULT_PRODUCT_NAME = "NanZi · 数据服务平台"
DEFAULT_LOGIN_SUBTITLE = "NanZi API Data Platform"
DEFAULT_ICON_URL = "/favicon.png"


class BrandingSettingsService:
    CONFIG_ENABLED = "branding.enabled"
    CONFIG_PRODUCT_NAME = "branding.product_name"
    CONFIG_LOGIN_SUBTITLE = "branding.login_subtitle"
    CONFIG_ICON_URL = "branding.icon_url"
    CONFIG_HIDE_LOGIN_SSO = "branding.hide_login_sso"
    CONFIG_HIDE_VERSION_LINK = "branding.hide_version_link"
    CONFIG_CONTACT_MARKDOWN = "branding.contact_markdown"
    CONFIG_COPYRIGHT_TEXT = "branding.copyright_text"

    @classmethod
    async def get_raw_settings(cls) -> Dict[str, Any]:
        return {
            "enabled": await SystemService.get_bool_config(cls.CONFIG_ENABLED, False),
            "product_name": (await SystemService.get_config(cls.CONFIG_PRODUCT_NAME, DEFAULT_PRODUCT_NAME) or "").strip()
            or DEFAULT_PRODUCT_NAME,
            "login_subtitle": (await SystemService.get_config(cls.CONFIG_LOGIN_SUBTITLE, DEFAULT_LOGIN_SUBTITLE) or "").strip()
            or DEFAULT_LOGIN_SUBTITLE,
            "icon_url": (await SystemService.get_config(cls.CONFIG_ICON_URL, DEFAULT_ICON_URL) or "").strip()
            or DEFAULT_ICON_URL,
            "hide_login_sso": await SystemService.get_bool_config(cls.CONFIG_HIDE_LOGIN_SSO, False),
            "hide_version_link": await SystemService.get_bool_config(cls.CONFIG_HIDE_VERSION_LINK, False),
            "contact_markdown": (await SystemService.get_config(cls.CONFIG_CONTACT_MARKDOWN, "")) or "",
            "copyright_text": (await SystemService.get_config(cls.CONFIG_COPYRIGHT_TEXT, "")) or "",
        }

    @classmethod
    async def get_public_branding(cls) -> Dict[str, Any]:
        """前端展示用：未启用个性化时返回默认品牌，开关项均为默认展示行为。"""
        raw = await cls.get_raw_settings()
        if not raw["enabled"]:
            return {
                "enabled": False,
                "product_name": DEFAULT_PRODUCT_NAME,
                "login_subtitle": DEFAULT_LOGIN_SUBTITLE,
                "icon_url": DEFAULT_ICON_URL,
                "hide_login_sso": False,
                "hide_version_link": False,
                "contact_markdown": "",
                "copyright_text": "",
            }
        return {
            "enabled": True,
            "product_name": raw["product_name"],
            "login_subtitle": raw["login_subtitle"],
            "icon_url": raw["icon_url"],
            "hide_login_sso": raw["hide_login_sso"],
            "hide_version_link": raw["hide_version_link"],
            "contact_markdown": raw["contact_markdown"],
            "copyright_text": raw["copyright_text"],
        }

    @classmethod
    async def update_settings(
        cls,
        *,
        enabled: bool,
        product_name: str,
        login_subtitle: str,
        icon_url: str,
        hide_login_sso: bool,
        hide_version_link: bool,
        contact_markdown: str,
        copyright_text: str,
    ) -> None:
        await SystemService.set_config(
            cls.CONFIG_ENABLED,
            "true" if enabled else "false",
            "branding",
        )
        await SystemService.set_config(
            cls.CONFIG_PRODUCT_NAME,
            (product_name or DEFAULT_PRODUCT_NAME).strip(),
            "branding",
        )
        await SystemService.set_config(
            cls.CONFIG_LOGIN_SUBTITLE,
            (login_subtitle or DEFAULT_LOGIN_SUBTITLE).strip(),
            "branding",
        )
        await SystemService.set_config(
            cls.CONFIG_ICON_URL,
            (icon_url or DEFAULT_ICON_URL).strip(),
            "branding",
        )
        await SystemService.set_config(
            cls.CONFIG_HIDE_LOGIN_SSO,
            "true" if hide_login_sso else "false",
            "branding",
        )
        await SystemService.set_config(
            cls.CONFIG_HIDE_VERSION_LINK,
            "true" if hide_version_link else "false",
            "branding",
        )
        await SystemService.set_config(
            cls.CONFIG_CONTACT_MARKDOWN,
            contact_markdown or "",
            "branding",
        )
        await SystemService.set_config(
            cls.CONFIG_COPYRIGHT_TEXT,
            copyright_text or "",
            "branding",
        )
