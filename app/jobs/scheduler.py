"""Background job scheduler with optional Redis distributed locking."""
from __future__ import annotations

import logging
from functools import wraps
from typing import Awaitable, Callable, TypeVar

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.core.config import settings
from app.core import redis

logger = logging.getLogger(__name__)

_scheduler: AsyncIOScheduler | None = None

T = TypeVar("T")


def with_scheduler_lock(job_name: str, ttl_seconds: int = 120):
    """Ensure only one worker runs a scheduled job when Redis is available."""

    def decorator(func: Callable[..., Awaitable[T]]):
        @wraps(func)
        async def wrapper(*args, **kwargs) -> T | None:
            r = await redis.get_redis()
            lock_key = f"scheduler:lock:{job_name}"

            if r:
                acquired = await r.set(lock_key, "1", nx=True, ex=ttl_seconds)
                if not acquired:
                    logger.debug("Skip job %s: lock held by another worker", job_name)
                    return None
                try:
                    return await func(*args, **kwargs)
                finally:
                    await r.delete(lock_key)

            return await func(*args, **kwargs)

        return wrapper

    return decorator


def get_scheduler() -> AsyncIOScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = AsyncIOScheduler()
    return _scheduler


def start_scheduler() -> None:
    if not settings.ENABLE_SCHEDULER:
        logger.info("Scheduler disabled (ENABLE_SCHEDULER=0)")
        return

    from app.jobs.aggregator import aggregate_access_logs
    from app.jobs.cleaner import clean_old_access_logs

    scheduler = get_scheduler()
    if scheduler.running:
        return

    locked_aggregate = with_scheduler_lock("aggregate_access_logs", ttl_seconds=90)(
        aggregate_access_logs
    )
    locked_clean = with_scheduler_lock("clean_old_access_logs", ttl_seconds=3600)(
        clean_old_access_logs
    )

    scheduler.add_job(locked_aggregate, "cron", minute="*", id="aggregate_access_logs")
    scheduler.add_job(locked_clean, "cron", hour=3, minute=0, id="clean_old_access_logs")
    scheduler.start()
    logger.info("Scheduler started with Redis lock deduplication")


def shutdown_scheduler() -> None:
    scheduler = get_scheduler()
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped")
