"""SQL Server 适配器单元测试（Mock 连接池，无需真实数据库）。"""
import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.data_adapter.factory import get_adapter
from app.services.data_adapter.models import LogicalQuery
from app.services.data_adapter.sqlserver import SqlServerAdapter
from app.schemas.resource import FieldConfig, ResourceResponse


@pytest.fixture
def mock_config():
    return ResourceResponse(
        id=1,
        created_at=datetime.now(),
        updated_at=datetime.now(),
        resource_key="test_resource",
        resource_name="Test",
        resource_group="TestGroup",
        resource_mode="TABLE",
        table_name="test_table",
        fields_config=[
            FieldConfig(name="id", type="INT", label="ID"),
            FieldConfig(name="name", type="VARCHAR", label="Name"),
        ],
        allowed_filters=[FieldConfig(name="id", type="INT", label="ID")],
        default_sort="id",
        status=1,
    )


def _mock_pool_with_cursor(mock_cursor: AsyncMock):
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
    return mock_pool


@pytest.mark.asyncio
async def test_sqlserver_adapter_sort_by_protection(mock_config):
    adapter = SqlServerAdapter(source_id=1)
    query_valid = LogicalQuery(resource="test_resource", sort_by="name", sort_order="asc")
    query_malicious = LogicalQuery(
        resource="test_resource",
        sort_by="id]; DROP TABLE users; --",
        sort_order="desc",
    )

    mock_cursor = AsyncMock()
    mock_cursor.fetchall.return_value = []
    mock_cursor.description = [("id",), ("name",)]

    with patch("app.services.meta_service.MetaService.get_config", new_callable=AsyncMock) as mock_get_config, patch(
        "app.services.pool_manager.DataSourcePoolManager.get_pool", new_callable=AsyncMock
    ) as mock_get_pool:
        mock_get_config.return_value = mock_config
        mock_get_pool.return_value = _mock_pool_with_cursor(mock_cursor)

        await adapter.execute(query_valid)
        sql = mock_cursor.execute.call_args[0][0]
        assert "ORDER BY [name] ASC" in sql
        assert "OFFSET ? ROWS FETCH NEXT ? ROWS ONLY" in sql

        await adapter.execute(query_malicious)
        sql = mock_cursor.execute.call_args[0][0]
        assert "ORDER BY [id] DESC" in sql
        assert "DROP TABLE" not in sql


@pytest.mark.asyncio
async def test_sqlserver_get_tables():
    adapter = SqlServerAdapter(source_id=1)
    mock_cursor = AsyncMock()
    mock_cursor.fetchall.return_value = [
        ("orders", "BASE TABLE"),
        ("order_view", "VIEW"),
    ]

    with patch(
        "app.services.pool_manager.DataSourcePoolManager.get_pool", new_callable=AsyncMock
    ) as mock_get_pool:
        mock_get_pool.return_value = _mock_pool_with_cursor(mock_cursor)
        tables = await adapter.get_tables()

    assert tables == [
        {"name": "orders", "type": "TABLE"},
        {"name": "order_view", "type": "VIEW"},
    ]
    sql = mock_cursor.execute.call_args[0][0]
    assert "INFORMATION_SCHEMA.TABLES" in sql


@pytest.mark.asyncio
async def test_sqlserver_build_where_operators():
    adapter = SqlServerAdapter(source_id=1)
    query = LogicalQuery(
        resource="test_resource",
        filters=[("id", "=", 1), ("id", "IN", [1, 2])],
    )
    where_sql, params = adapter._build_where(query, ResourceResponse(
        id=1,
        created_at=datetime.now(),
        updated_at=datetime.now(),
        resource_key="k",
        resource_name="n",
        resource_group="g",
        resource_mode="TABLE",
        table_name="t",
        fields_config=[],
        allowed_filters=[FieldConfig(name="id", type="INT", label="ID")],
        default_sort="id",
        status=1,
    ))
    assert "[id] = ?" in where_sql
    assert "[id] IN (?, ?)" in where_sql
    assert params == (1, 1, 2)


def test_build_sqlserver_dsn():
    from types import SimpleNamespace
    from app.services.pool_manager import DataSourcePoolManager

    ds = SimpleNamespace(
        host="sql.example.com",
        port=1433,
        database_name="warehouse",
        username="sa",
        password="secret",
        extra_params={"trust_server_certificate": True, "odbc_driver": "ODBC Driver 18 for SQL Server"},
    )
    with patch("app.services.pool_manager.aioodbc", MagicMock()):
        dsn = DataSourcePoolManager._build_sqlserver_dsn(ds)
    assert "DRIVER={ODBC Driver 18 for SQL Server}" in dsn
    assert "SERVER=sql.example.com,1433" in dsn
    assert "DATABASE=warehouse" in dsn
    assert "UID=sa" in dsn
    assert "Encrypt=no" in dsn
    assert "TrustServerCertificate=yes" in dsn


def test_build_sqlserver_dsn_encrypt_enabled():
    from types import SimpleNamespace
    from app.services.pool_manager import DataSourcePoolManager

    ds = SimpleNamespace(
        host="sql.example.com",
        port=1433,
        database_name="warehouse",
        username="sa",
        password="secret",
        extra_params={"encrypt": True, "trust_server_certificate": False},
    )
    with patch("app.services.pool_manager.aioodbc", MagicMock()):
        dsn = DataSourcePoolManager._build_sqlserver_dsn(ds)
    assert "Encrypt=yes" in dsn
    assert "TrustServerCertificate" not in dsn


@pytest.mark.asyncio
async def test_factory_returns_sqlserver_adapter():
    from types import SimpleNamespace

    ds = SimpleNamespace(id=99, source_type="sqlserver", status=1)
    with patch(
        "app.services.datasource_service.DataSourceService.get_datasource_by_name",
        new_callable=AsyncMock,
        return_value=ds,
    ):
        adapter = await get_adapter("mssql_prod")
    assert isinstance(adapter, SqlServerAdapter)
    assert adapter.source_id == 99
