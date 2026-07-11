import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.db_profile_service import (
    DbProfileService,
    PROFILE_CANCEL_MESSAGE,
    _TASK_STATUS_DONE,
    _TASK_STATUS_RUNNING,
)


@pytest.mark.parametrize(
    "task,expected",
    [
        (None, False),
        ({"status": 1}, False),
        ({"status": 3, "error_message": PROFILE_CANCEL_MESSAGE}, True),
        ({"status": 3, "error_message": "连接超时"}, False),
    ],
)
def test_is_cancelled_task(task, expected):
    assert DbProfileService.is_cancelled_task(task) is expected


@pytest.mark.asyncio
async def test_cancel_profiling_task_success():
    running_task = {
        "id": 1,
        "connection_id": 10,
        "status": 1,
        "total_tables": 100,
        "processed_tables": 42,
        "current_table": "FOO",
        "error_message": None,
        "created_at": "2026-07-11T00:00:00",
        "updated_at": "2026-07-11T00:00:00",
    }
    cancelled_task = {**running_task, "status": 3, "error_message": PROFILE_CANCEL_MESSAGE, "current_table": None}

    mock_cursor = AsyncMock()
    mock_cursor.rowcount = 1
    mock_cursor_cm = AsyncMock()
    mock_cursor_cm.__aenter__.return_value = mock_cursor
    mock_cursor_cm.__aexit__.return_value = None

    mock_conn = MagicMock()
    mock_conn.cursor.return_value = mock_cursor_cm
    mock_conn.commit = AsyncMock()
    mock_conn_cm = AsyncMock()
    mock_conn_cm.__aenter__.return_value = mock_conn
    mock_conn_cm.__aexit__.return_value = None

    with patch(
        "app.services.db_profile_service.get_db_connection",
        return_value=mock_conn_cm,
    ), patch.object(
        DbProfileService,
        "get_task_status",
        new=AsyncMock(side_effect=[running_task, cancelled_task]),
    ):
        result = await DbProfileService.cancel_profiling_task(10)

    assert result["status"] == 3
    assert result["error_message"] == PROFILE_CANCEL_MESSAGE
    assert mock_cursor.execute.await_count == 2


@pytest.mark.asyncio
async def test_cancel_profiling_task_rejects_when_not_running():
    with patch.object(
        DbProfileService,
        "get_task_status",
        new=AsyncMock(return_value={"status": 2}),
    ):
        with pytest.raises(ValueError, match="没有进行中的摸排任务"):
            await DbProfileService.cancel_profiling_task(10)


@pytest.mark.parametrize(
    "col_type,expected",
    [
        ("VARCHAR2(100)", False),
        ("CLOB", True),
        ("BLOB", True),
        ("LONG RAW", True),
        ("NUMBER", False),
    ],
)
def test_is_heavy_column_type(col_type, expected):
    assert DbProfileService._is_heavy_column_type(col_type) is expected


@pytest.mark.asyncio
async def test_build_sample_query_skips_heavy_columns():
    adapter = AsyncMock()
    adapter.get_columns = AsyncMock(return_value=[
        {"name": "ID", "type": "NUMBER"},
        {"name": "DOC", "type": "CLOB"},
        {"name": "TITLE", "type": "VARCHAR2(200)"},
    ])

    sql = await DbProfileService._build_sample_query(adapter, "oracle", "MY_TABLE")

    assert '"ID"' in sql
    assert '"TITLE"' in sql
    assert "DOC" not in sql
    assert "ROWNUM <= 3" in sql


@pytest.mark.asyncio
async def test_build_sample_query_fallback_to_star():
    adapter = AsyncMock()
    adapter.get_columns = AsyncMock(side_effect=RuntimeError("metadata unavailable"))

    sql = await DbProfileService._build_sample_query(adapter, "mysql", "users")

    assert "SELECT * FROM `users` LIMIT 3" == sql


@pytest.mark.asyncio
async def test_bulk_init_table_profiles_force_resets_completed():
    mock_cursor = AsyncMock()
    existing_profiles = {"T1": 1, "T2": 2}
    tables_info = [{"name": "T1", "type": "table"}, {"name": "T2", "type": "table"}]

    await DbProfileService._bulk_init_table_profiles(
        mock_cursor, 10, tables_info, existing_profiles, force=True
    )

    update_sql = mock_cursor.executemany.await_args_list[0][0][0]
    assert "status != 2" not in update_sql
    assert mock_cursor.executemany.await_count == 1


@pytest.mark.asyncio
async def test_bulk_init_table_profiles_resume_skips_completed():
    mock_cursor = AsyncMock()
    existing_profiles = {"T1": 1}
    tables_info = [{"name": "T1", "type": "table"}]

    await DbProfileService._bulk_init_table_profiles(
        mock_cursor, 10, tables_info, existing_profiles, force=False
    )

    update_sql = mock_cursor.executemany.await_args_list[0][0][0]
    assert "status != 2" in update_sql


@pytest.mark.asyncio
async def test_reconcile_marks_main_task_done_when_all_tables_finished():
    mock_cursor = AsyncMock()
    mock_cursor.rowcount = 1

    # zombie reset
    mock_cursor.fetchone.side_effect = [
        (_TASK_STATUS_RUNNING, 100),  # task row
    ]
    mock_cursor.fetchall.return_value = [(2, 80), (3, 20)]  # success + failed, no pending/in_progress

    changed = await DbProfileService._reconcile_profiling_task_status_with_cursor(mock_cursor, 10)

    assert changed is True
    finalize_sql = mock_cursor.execute.await_args_list[-1][0][0]
    assert "SET status = %s" in finalize_sql or "status = %s" in finalize_sql
    finalize_params = mock_cursor.execute.await_args_list[-1][0][1]
    assert finalize_params[0] == _TASK_STATUS_DONE
    assert finalize_params[1] == 100


@pytest.mark.asyncio
async def test_reconcile_skips_when_tables_still_pending():
    mock_cursor = AsyncMock()
    mock_cursor.rowcount = 0
    mock_cursor.fetchone.return_value = (_TASK_STATUS_RUNNING, 100)
    mock_cursor.fetchall.return_value = [(0, 5), (2, 95)]

    changed = await DbProfileService._reconcile_profiling_task_status_with_cursor(mock_cursor, 10)

    assert changed is False
    assert mock_cursor.execute.await_count == 3  # zombie + task select + group by


@pytest.mark.asyncio
async def test_should_stop_profiling_when_cancelled():
    with patch.object(
        DbProfileService,
        "get_task_status",
        new=AsyncMock(return_value={"status": 3, "error_message": PROFILE_CANCEL_MESSAGE}),
    ):
        assert await DbProfileService._should_stop_profiling(10) is True

    with patch.object(
        DbProfileService,
        "get_task_status",
        new=AsyncMock(return_value={"status": 1}),
    ):
        assert await DbProfileService._should_stop_profiling(10) is False
