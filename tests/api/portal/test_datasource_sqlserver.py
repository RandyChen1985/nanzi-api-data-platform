"""SQL Server 数据源门户 API 测试（连接测试 Mock，无需真实库）。"""
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_sqlserver_datasource(client: AsyncClient, admin_api_key: str):
    name = f"test_sqlserver_{uuid.uuid4().hex[:8]}"
    headers = {"X-API-Key": admin_api_key}
    create = await client.post(
        "/api/portal/datasource/datasources",
        headers=headers,
        json={
            "source_name": name,
            "source_type": "sqlserver",
            "host": "127.0.0.1",
            "port": 1433,
            "database_name": "master",
            "username": "sa",
            "password": "test",
            "status": 1,
            "extra_params": {"trust_server_certificate": True},
        },
    )
    assert create.status_code == 200, create.text
    body = create.json()
    assert body["source_type"] == "sqlserver"
    assert body["port"] == 1433

    await client.delete(f"/api/portal/datasource/datasources/{body['id']}", headers=headers)


@pytest.mark.asyncio
async def test_sqlserver_connection_test_mocked(client: AsyncClient, admin_api_key: str):
    headers = {"X-API-Key": admin_api_key}
    name = f"test_sqlserver_conn_{uuid.uuid4().hex[:8]}"
    create = await client.post(
        "/api/portal/datasource/datasources",
        headers=headers,
        json={
            "source_name": name,
            "source_type": "sqlserver",
            "host": "127.0.0.1",
            "port": 1433,
            "database_name": "master",
            "status": 1,
        },
    )
    assert create.status_code == 200
    source_id = create.json()["id"]

    mock_cursor = AsyncMock()
    mock_cursor.fetchone = AsyncMock(return_value=(1,))
    mock_conn = MagicMock()
    mock_cursor_cm = MagicMock()
    mock_cursor_cm.__aenter__ = AsyncMock(return_value=mock_cursor)
    mock_cursor_cm.__aexit__ = AsyncMock()
    mock_conn.cursor.return_value = mock_cursor_cm
    mock_pool = MagicMock()
    mock_conn_cm = MagicMock()
    mock_conn_cm.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_conn_cm.__aexit__ = AsyncMock()
    mock_pool.acquire.return_value = mock_conn_cm

    with patch(
        "app.services.pool_manager.DataSourcePoolManager.get_pool",
        new_callable=AsyncMock,
        return_value=mock_pool,
    ):
        test_res = await client.post(
            f"/api/portal/datasource/datasources/{source_id}/test",
            headers=headers,
        )

    assert test_res.status_code == 200
    assert test_res.json()["status"] == "success"
    mock_cursor.execute.assert_awaited_with("SELECT 1")

    await client.delete(f"/api/portal/datasource/datasources/{source_id}", headers=headers)


@pytest.mark.asyncio
async def test_sqlserver_connection_test_uses_payload_extra_params(client: AsyncClient, admin_api_key: str):
    headers = {"X-API-Key": admin_api_key}
    mock_cursor = AsyncMock()
    mock_cursor.fetchone = AsyncMock(return_value=(1,))
    mock_conn = MagicMock()
    mock_cursor_cm = MagicMock()
    mock_cursor_cm.__aenter__ = AsyncMock(return_value=mock_cursor)
    mock_cursor_cm.__aexit__ = AsyncMock()
    mock_conn.cursor.return_value = mock_cursor_cm
    mock_pool = MagicMock()
    mock_conn_cm = MagicMock()
    mock_conn_cm.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_conn_cm.__aexit__ = AsyncMock()
    mock_pool.acquire.return_value = mock_conn_cm

    with patch(
        "app.services.pool_manager.DataSourcePoolManager.create_ephemeral_pool",
        new_callable=AsyncMock,
        return_value=mock_pool,
        create=True,
    ) as mock_create_pool:
        test_res = await client.post(
            "/api/portal/datasource/datasources/test-connection",
            headers=headers,
            json={
                "source_name": "sqlserver_unsaved",
                "source_type": "sqlserver",
                "host": "127.0.0.1",
                "port": 1433,
                "database_name": "master",
                "username": "sa",
                "password": "test",
                "status": 1,
                "extra_params": {
                    "encrypt": False,
                    "trust_server_certificate": True,
                    "odbc_driver": "ODBC Driver 18 for SQL Server",
                },
            },
        )

    assert test_res.status_code == 200
    assert test_res.json()["status"] == "success"
    datasource_arg = mock_create_pool.await_args.args[0]
    assert datasource_arg.extra_params["encrypt"] is False
    assert datasource_arg.extra_params["trust_server_certificate"] is True
    mock_cursor.execute.assert_awaited_with("SELECT 1")
