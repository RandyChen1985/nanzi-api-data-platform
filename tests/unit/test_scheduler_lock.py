"""Unit tests for background job scheduler locking."""
from unittest.mock import AsyncMock, patch

import pytest

from app.jobs.scheduler import with_scheduler_lock


@pytest.mark.asyncio
async def test_scheduler_lock_skips_when_lock_held():
    mock_redis = AsyncMock()
    mock_redis.set = AsyncMock(return_value=False)

    called = False

    @with_scheduler_lock("test_job")
    async def job():
        nonlocal called
        called = True

    with patch("app.jobs.scheduler.redis.get_redis", AsyncMock(return_value=mock_redis)):
        result = await job()

    assert result is None
    assert called is False


@pytest.mark.asyncio
async def test_scheduler_lock_runs_when_acquired():
    mock_redis = AsyncMock()
    mock_redis.set = AsyncMock(return_value=True)
    mock_redis.delete = AsyncMock()

    @with_scheduler_lock("test_job")
    async def job():
        return "done"

    with patch("app.jobs.scheduler.redis.get_redis", AsyncMock(return_value=mock_redis)):
        result = await job()

    assert result == "done"
    mock_redis.delete.assert_awaited_once()


@pytest.mark.asyncio
async def test_scheduler_lock_runs_without_redis():
    @with_scheduler_lock("test_job")
    async def job():
        return "ok"

    with patch("app.jobs.scheduler.redis.get_redis", AsyncMock(return_value=None)):
        assert await job() == "ok"
