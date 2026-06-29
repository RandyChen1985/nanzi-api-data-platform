"""Unit tests for audit log cleaner job."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.jobs import cleaner


@pytest.mark.asyncio
async def test_clean_old_logs_drops_expired_tables():
    mock_cursor = AsyncMock()
    mock_cursor.lastrowid = 1
    mock_cursor.fetchone = AsyncMock(side_effect=[
        ("7",),  # retention days
        None,
    ])
    mock_cursor.fetchall = AsyncMock(return_value=[
        ("api_access_logs_20200101",),
        ("api_access_logs_20990101",),
    ])
    mock_cursor.__aenter__ = AsyncMock(return_value=mock_cursor)
    mock_cursor.__aexit__ = AsyncMock(return_value=False)

    mock_conn = AsyncMock()
    mock_conn.cursor = MagicMock(return_value=mock_cursor)
    mock_conn.commit = AsyncMock()
    mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_conn.__aexit__ = AsyncMock(return_value=False)

    with patch("app.jobs.cleaner.get_db_connection", return_value=mock_conn):
        await cleaner.clean_old_access_logs(retention_days=7)

    drop_calls = [
        call for call in mock_cursor.execute.await_args_list
        if call.args and str(call.args[0]).startswith("DROP TABLE")
    ]
    assert len(drop_calls) == 1
    assert "20200101" in drop_calls[0].args[0]
