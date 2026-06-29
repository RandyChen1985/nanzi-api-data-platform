"""SSO authentication flow tests."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_sso_login_user_not_found(client: AsyncClient):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"data": {"token": "ok"}}

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("app.services.auth_service.httpx.AsyncClient", return_value=mock_client):
        response = await client.post(
            "/api/portal/auth/sso/login",
            json={"username": "unknown_sso_user", "password": "secret"},
        )

    assert response.status_code == 401
    assert "开通" in response.json().get("detail", "")


@pytest.mark.asyncio
async def test_sso_api_timeout_returns_error(client: AsyncClient):
    import httpx as httpx_lib

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(side_effect=httpx_lib.TimeoutException("timeout"))
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("app.services.auth_service.httpx.AsyncClient", return_value=mock_client):
        response = await client.post(
            "/api/portal/auth/sso/login",
            json={"username": "admin", "password": "wrong"},
        )

    assert response.status_code in (401, 400, 422, 500)
