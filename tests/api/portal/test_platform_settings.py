"""平台系统配置与钉钉审批通知测试"""
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from app.services.dingtalk_notification_service import DingTalkNotificationService


@pytest.fixture(autouse=True)
async def ensure_dingtalk_config():
    from app.core.database import get_db_connection

    keys = (
        ("notify.dingtalk.enabled", "true"),
        ("notify.dingtalk.webhook_url", "https://example.com/robot/send?access_token=test"),
        ("notify.dingtalk.secret", ""),
        ("notify.dingtalk.on_request", "true"),
        ("notify.dingtalk.on_result", "true"),
    )
    async with get_db_connection() as conn:
        async with conn.cursor() as cursor:
            for key, value in keys:
                await cursor.execute(
                    """
                    INSERT INTO sys_config (config_key, config_value, config_group)
                    VALUES (%s, %s, 'notify')
                    ON DUPLICATE KEY UPDATE config_value = VALUES(config_value)
                    """,
                    (key, value),
                )
        await conn.commit()


@pytest.mark.asyncio
async def test_platform_settings_get_and_update(client: AsyncClient, admin_api_key: str):
    headers = {"X-API-Key": admin_api_key}
    res = await client.get("/api/portal/system/platform-settings", headers=headers)
    assert res.status_code == 200
    body = res.json()
    assert "catalog" in body
    assert "dingtalk" in body
    assert "mcp" in body
    assert "default_owner_strategy" in body["catalog"]

    update = await client.put(
        "/api/portal/system/platform-settings",
        headers=headers,
        json={
            "dingtalk": {
                "enabled": True,
                "webhook_url": "https://oapi.dingtalk.com/robot/send?access_token=abc",
                "secret": "SEC123",
                "notify_on_request": True,
                "notify_on_result": False,
            }
        },
    )
    assert update.status_code == 200
    dingtalk = update.json()["dingtalk"]
    assert dingtalk["enabled"] is True
    assert dingtalk["webhook_url"].startswith("https://oapi.dingtalk.com")
    assert dingtalk["notify_on_result"] is False


@pytest.mark.asyncio
async def test_dingtalk_send_markdown(client: AsyncClient, admin_api_key: str):
    headers = {"X-API-Key": admin_api_key}

    mock_response = AsyncMock()
    mock_response.raise_for_status = lambda: None
    mock_response.json = lambda: {"errcode": 0}

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch(
        "app.services.dingtalk_notification_service.httpx.AsyncClient",
        return_value=mock_client,
    ):
        ok, _ = await DingTalkNotificationService.send_test_message(
            {
                "enabled": True,
                "webhook_url": "https://example.com/robot/send?access_token=test",
                "secret": "",
            }
        )
        assert ok is True
        assert mock_client.post.called

        test_api = await client.post(
            "/api/portal/system/platform-settings/dingtalk/test",
            headers=headers,
            json={
                "enabled": True,
                "webhook_url": "https://example.com/robot/send?access_token=test",
                "secret": "",
                "notify_on_request": True,
                "notify_on_result": True,
            },
        )
        assert test_api.status_code == 200


@pytest.mark.asyncio
async def test_mcp_test_disabled(client: AsyncClient, admin_api_key: str):
    headers = {"X-API-Key": admin_api_key}
    res = await client.post(
        "/api/portal/system/platform-settings/mcp/test",
        headers=headers,
        json={"enabled": False},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["success"] is False
    assert any(c["name"] == "服务开关" and c["ok"] is False for c in body["checks"])


@pytest.mark.asyncio
async def test_mcp_test_enabled(client: AsyncClient, admin_api_key: str):
    headers = {"X-API-Key": admin_api_key}
    res = await client.post(
        "/api/portal/system/platform-settings/mcp/test",
        headers=headers,
        json={"enabled": True},
    )
    assert res.status_code == 200
    body = res.json()
    assert "checks" in body
    assert "yunshu_list_resources" in body.get("tools", [])
    sdk_check = next(c for c in body["checks"] if c["name"] == "MCP SDK")
    assert sdk_check["ok"] is True


@pytest.mark.asyncio
async def test_access_request_triggers_dingtalk(client: AsyncClient, admin_api_key: str, valid_api_key: str):
    headers = {"X-API-Key": admin_api_key}
    user_headers = {"X-API-Key": valid_api_key}

    resources = await client.get("/api/portal/meta/resources", headers=headers)
    target = next(
        (
            r
            for r in resources.json()
            if r.get("resource_group", "").lower() != "system"
            and r.get("resource_mode") in ("TABLE", "SQL")
        ),
        None,
    )
    if not target:
        pytest.skip("无可用非系统资源")

    await client.post(
        "/api/portal/catalog/products/publish-from-resource",
        headers=headers,
        json={"resource_key": target["resource_key"], "publish": True},
    )

    with patch.object(
        DingTalkNotificationService,
        "notify_access_request_created",
        new_callable=AsyncMock,
    ) as mock_notify:
        create = await client.post(
            f"/api/portal/catalog/products/{target['resource_key']}/access-request",
            headers=user_headers,
            json={"message": "需要访问做报表"},
        )
        if create.status_code == 400 and "已拥有" in create.text:
            pytest.skip("用户已有权限")
        assert create.status_code == 200, create.text
        assert mock_notify.called
