import base64
import hashlib
import hmac
import logging
import time
import urllib.parse
from typing import Any, Dict, Optional

import httpx

from app.services.system_service import SystemService

logger = logging.getLogger(__name__)


class DingTalkNotificationService:
    CONFIG_ENABLED = "notify.dingtalk.enabled"
    CONFIG_WEBHOOK = "notify.dingtalk.webhook_url"
    CONFIG_SECRET = "notify.dingtalk.secret"
    CONFIG_ON_REQUEST = "notify.dingtalk.on_request"
    CONFIG_ON_RESULT = "notify.dingtalk.on_result"

    @classmethod
    async def get_settings(cls) -> Dict[str, Any]:
        return {
            "enabled": await SystemService.get_bool_config(cls.CONFIG_ENABLED, False),
            "webhook_url": (await SystemService.get_config(cls.CONFIG_WEBHOOK, "")) or "",
            "secret": (await SystemService.get_config(cls.CONFIG_SECRET, "")) or "",
            "notify_on_request": await SystemService.get_bool_config(cls.CONFIG_ON_REQUEST, True),
            "notify_on_result": await SystemService.get_bool_config(cls.CONFIG_ON_RESULT, True),
        }

    @classmethod
    async def update_settings(
        cls,
        *,
        enabled: bool,
        webhook_url: str,
        secret: str,
        notify_on_request: bool,
        notify_on_result: bool,
    ) -> None:
        await SystemService.set_config(cls.CONFIG_ENABLED, "true" if enabled else "false", "notify")
        await SystemService.set_config(cls.CONFIG_WEBHOOK, (webhook_url or "").strip(), "notify")
        await SystemService.set_config(cls.CONFIG_SECRET, (secret or "").strip(), "notify")
        await SystemService.set_config(
            cls.CONFIG_ON_REQUEST, "true" if notify_on_request else "false", "notify"
        )
        await SystemService.set_config(
            cls.CONFIG_ON_RESULT, "true" if notify_on_result else "false", "notify"
        )

    @classmethod
    async def _is_ready(cls) -> bool:
        cfg = await cls.get_settings()
        return bool(cfg["enabled"] and (cfg["webhook_url"] or "").strip())

    @classmethod
    def _signed_webhook_url(cls, webhook_url: str, secret: str) -> str:
        url = webhook_url.strip()
        if not secret.strip():
            return url
        timestamp = str(round(time.time() * 1000))
        string_to_sign = f"{timestamp}\n{secret.strip()}"
        digest = hmac.new(
            secret.strip().encode("utf-8"),
            string_to_sign.encode("utf-8"),
            digestmod=hashlib.sha256,
        ).digest()
        sign = urllib.parse.quote_plus(base64.b64encode(digest))
        separator = "&" if "?" in url else "?"
        return f"{url}{separator}timestamp={timestamp}&sign={sign}"

    @classmethod
    async def send_markdown(cls, title: str, text: str) -> bool:
        cfg = await cls.get_settings()
        webhook_url = (cfg.get("webhook_url") or "").strip()
        if not cfg.get("enabled") or not webhook_url:
            return False
        signed_url = cls._signed_webhook_url(webhook_url, cfg.get("secret") or "")
        payload = {
            "msgtype": "markdown",
            "markdown": {"title": title, "text": text},
        }
        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                response = await client.post(signed_url, json=payload)
                response.raise_for_status()
                body = response.json()
                if isinstance(body, dict) and body.get("errcode") not in (0, None):
                    logger.warning("DingTalk API error: %s", body)
                    return False
                return True
        except Exception as e:
            logger.warning("DingTalk notification failed: %s", e)
            return False

    @classmethod
    async def send_test_message(cls) -> bool:
        return await cls.send_markdown(
            "云枢数据平台",
            "### 钉钉通知测试\n\n这是一条来自**云枢 · 数据服务平台**的测试消息，说明机器人配置可用。",
        )

    @classmethod
    async def notify_access_request_created(
        cls,
        *,
        request_id: int,
        product_key: str,
        product_name: str,
        applicant_name: str,
        message: Optional[str] = None,
    ) -> None:
        cfg = await cls.get_settings()
        if not cfg["enabled"] or not cfg["notify_on_request"]:
            return
        lines = [
            "### 目录权限申请",
            f"- **产品**：{product_name} (`{product_key}`)",
            f"- **申请人**：{applicant_name}",
            f"- **申请单号**：#{request_id}",
        ]
        if message:
            lines.append(f"- **申请说明**：{message}")
        lines.append("\n请负责人尽快登录平台处理。")
        await cls.send_markdown("目录权限申请", "\n".join(lines))

    @classmethod
    async def notify_access_request_handled(
        cls,
        *,
        request_id: int,
        product_key: str,
        product_name: str,
        applicant_name: str,
        approved: bool,
        handler_name: str,
        remark: Optional[str] = None,
    ) -> None:
        cfg = await cls.get_settings()
        if not cfg["enabled"] or not cfg["notify_on_result"]:
            return
        status = "已通过" if approved else "已拒绝"
        lines = [
            f"### 目录权限审批{status}",
            f"- **产品**：{product_name} (`{product_key}`)",
            f"- **申请人**：{applicant_name}",
            f"- **审批人**：{handler_name}",
            f"- **申请单号**：#{request_id}",
        ]
        if remark:
            lines.append(f"- **审批备注**：{remark}")
        await cls.send_markdown(f"目录权限审批{status}", "\n".join(lines))
