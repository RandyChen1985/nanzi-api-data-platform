"""GET /api/v1/resources 与 MCP status 测试"""
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient


@pytest.fixture
def mock_auth_service():
    with patch("app.services.auth_service.AuthService.verify_api_key", new_callable=AsyncMock) as mock:
        yield mock


@pytest.fixture
def mock_rate_limit():
    with patch("app.core.dependencies.check_rate_limit", new_callable=AsyncMock):
        yield


@pytest.mark.asyncio
async def test_mcp_status_default_disabled(client: AsyncClient):
    res = await client.get("/api/v1/mcp/status")
    assert res.status_code == 200
    body = res.json()
    assert "enabled" in body
    assert body["sse_path"] == "/mcp/sse"


@pytest.mark.asyncio
async def test_list_resources_requires_auth(client: AsyncClient, mock_rate_limit):
    res = await client.get("/api/v1/resources")
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_list_resources_for_user(
    client: AsyncClient, mock_auth_service, mock_rate_limit
):
    from app.core.database import get_db_connection
    from app.schemas.auth import PermissionSet, UserPermissionsResponse

    async with get_db_connection() as conn:
        async with conn.cursor() as cursor:
            await cursor.execute("SELECT id FROM api_users WHERE user_name = 'test_user'")
            row = await cursor.fetchone()
            user_id = int(row[0]) if row else 2

    mock_auth_service.return_value = {
        "user_id": str(user_id),
        "user_name": "test_user",
        "role": "user",
        "status": 1,
    }

    perms = UserPermissionsResponse(
        user_id=user_id,
        username="test_user",
        role="user",
        business_roles=[],
        permissions=PermissionSet(
            menus=[],
            elements=[],
            resources=["test_donghuan_real_metrics"],
            datasources=[],
            data_tables=[],
        ),
    )

    with patch(
        "app.services.permission_service.PermissionService.get_user_permissions",
        new_callable=AsyncMock,
        return_value=perms,
    ):
        res = await client.get(
            "/api/v1/resources",
            headers={"X-API-Key": "mock-key"},
        )

    assert res.status_code == 200
    body = res.json()
    assert body["code"] == 200
    keys = [i["resource_key"] for i in body["data"]["items"]]
    assert "test_donghuan_real_metrics" in keys
    assert len(keys) == 1


@pytest.mark.asyncio
async def test_platform_settings_mcp_update(client: AsyncClient, admin_api_key: str):
    headers = {"X-API-Key": admin_api_key}
    res = await client.get("/api/portal/system/platform-settings", headers=headers)
    assert res.status_code == 200
    assert "mcp" in res.json()

    update = await client.put(
        "/api/portal/system/platform-settings",
        headers=headers,
        json={
            "mcp": {
                "enabled": True,
                "instructions": "测试 MCP 说明",
            }
        },
    )
    assert update.status_code == 200
    mcp = update.json()["mcp"]
    assert mcp["enabled"] is True
    assert mcp["instructions"] == "测试 MCP 说明"
    assert mcp["public_base_url"] == "http://testserver"
    assert mcp["sse_url"] == "http://testserver/mcp/sse"

    status = await client.get("/api/v1/mcp/status")
    status_body = status.json()
    assert status_body["enabled"] is True
    assert status_body["sse_url"] == "http://testserver/mcp/sse"
