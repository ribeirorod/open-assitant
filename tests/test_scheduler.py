# tests/test_scheduler.py
import pytest
from unittest.mock import AsyncMock, patch
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import asyncio


def test_scheduler_job_is_coroutine_function():
    """Scheduled jobs must be registered as coroutine functions, not anyio wrappers."""
    import inspect
    from src.scheduler.scheduler import _run_task
    assert inspect.iscoroutinefunction(_run_task), "_run_task must be a coroutine function"


@pytest.mark.asyncio
async def test_start_scheduler_returns_running_scheduler(tmp_path, monkeypatch):
    """Scheduler starts even when no schedules.yaml exists."""
    from src.scheduler import scheduler as sched_mod
    monkeypatch.setattr(sched_mod, "SCHEDULES_PATH", tmp_path / "schedules.yaml")
    s = sched_mod.start_scheduler()
    assert s.running
    s.shutdown(wait=False)
