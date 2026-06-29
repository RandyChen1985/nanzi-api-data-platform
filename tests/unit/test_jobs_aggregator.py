"""Unit tests for access log aggregation job."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.jobs import aggregator


@pytest.mark.asyncio
async def test_aggregate_skips_missing_table():
    mock_cursor = AsyncMock()
    mock_cursor.execute = AsyncMock(side_effect=Exception("Table doesn't exist"))
    mock_cursor.__aenter__ = AsyncMock(return_value=mock_cursor)
    mock_cursor.__aexit__ = AsyncMock(return_value=False)

    mock_conn = AsyncMock()
    mock_conn.cursor = MagicMock(return_value=mock_cursor)
    mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_conn.__aexit__ = AsyncMock(return_value=False)

    with patch("app.jobs.aggregator.get_db_connection", return_value=mock_conn):
        await aggregator.aggregate_access_logs()

    mock_cursor.execute.assert_awaited()


@pytest.mark.asyncio
async def test_aggregate_success():
    mock_cursor = AsyncMock()
    mock_cursor.rowcount = 3
    mock_cursor.__aenter__ = AsyncMock(return_value=mock_cursor)
    mock_cursor.__aexit__ = AsyncMock(return_value=False)

    mock_conn = AsyncMock()
    mock_conn.cursor = MagicMock(return_value=mock_cursor)
    mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_conn.__aexit__ = AsyncMock(return_value=False)

    with patch("app.jobs.aggregator.get_db_connection", return_value=mock_conn):
        await aggregator.aggregate_access_logs()

    assert mock_cursor.execute.await_count == 2
