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


@pytest.mark.asyncio
async def test_run_task_skips_notification_on_empty_response():
    """_run_task must not notify when agent returns empty or sentinel response."""
    task = {
        "name": "pulse",
        "prompt": "Run the /pulse skill.",
        "notify": {"telegram": ["123456789"]},
    }
    for empty_response in ["", "   ", "(no response)"]:
        with patch("src.scheduler.scheduler.ask_agent", new=AsyncMock(return_value=empty_response)), \
             patch("src.channels.telegram_notify.send_telegram_message", new=AsyncMock()) as mock_send:
            from src.scheduler import scheduler as sched_mod
            await sched_mod._run_task(task)
            assert not mock_send.await_count, f"should not notify for response={empty_response!r}"


@pytest.mark.asyncio
async def test_run_task_sends_notification_on_non_empty_response():
    """_run_task must call send_telegram_message when agent returns content."""
    task = {
        "name": "morning-briefing",
        "prompt": "Give me a briefing.",
        "notify": {"telegram": ["123456789"]},
    }
    # Import module before patching so patch() can resolve src.scheduler.scheduler.ask_agent
    from src.scheduler import scheduler as sched_mod  # noqa: F401 — ensures module is in sys.modules
    with patch("src.scheduler.scheduler.ask_agent", new=AsyncMock(return_value="1. Check email")), \
         patch("src.channels.telegram_notify.send_telegram_message", new=AsyncMock()) as mock_send:
        await sched_mod._run_task(task)
        mock_send.assert_awaited_once_with("123456789", "1. Check email")
