"""Scheduled tasks that run on a cron-like schedule.

Workflow: Scheduled task -> Claude Agent -> Google Workspace -> Telegram|WhatsApp -> User

Tasks are defined in a YAML config file (~/.open-assistant/schedules.yaml).
Example:

```yaml
tasks:
  - name: morning-briefing
    cron: "0 8 * * 1-5"          # weekdays at 8am
    prompt: "Give me a morning briefing: unread emails, today's calendar, and pending tasks."
    notify:
      telegram: ["123456789"]     # chat IDs
      whatsapp: ["15551234567"]   # phone numbers

  - name: weekly-report
    cron: "0 17 * * 5"            # Fridays at 5pm
    prompt: "Summarize this week's calendar events and any flagged emails."
    notify:
      telegram: ["123456789"]
```
"""

from __future__ import annotations

import logging
import pathlib

import anyio
import yaml
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from src.agent.core import ask_agent

log = logging.getLogger(__name__)

SCHEDULES_PATH = pathlib.Path.home() / ".open-assistant" / "schedules.yaml"


def _load_tasks() -> list[dict]:
    if not SCHEDULES_PATH.exists():
        log.info("No schedule file at %s — skipping.", SCHEDULES_PATH)
        return []
    data = yaml.safe_load(SCHEDULES_PATH.read_text()) or {}
    return data.get("tasks", [])


async def _run_task(task: dict) -> None:
    """Execute one scheduled task and fan out notifications."""
    name = task["name"]
    prompt = task["prompt"]
    log.info("scheduler: running task %s", name)

    response = await ask_agent(prompt, chat_id=f"sched:{name}")

    # Fan out to channels
    notify = task.get("notify", {})

    tg_ids = notify.get("telegram", [])
    if tg_ids:
        from src.channels.telegram_notify import send_telegram_message

        for chat_id in tg_ids:
            await send_telegram_message(str(chat_id), response)

    wa_numbers = notify.get("whatsapp", [])
    if wa_numbers:
        from src.channels.whatsapp import send_notification

        for number in wa_numbers:
            await send_notification(str(number), response)

    log.info("scheduler: task %s done, notified tg=%d wa=%d", name, len(tg_ids), len(wa_numbers))


def start_scheduler() -> AsyncIOScheduler:
    """Load schedule config, register jobs, and return the running scheduler."""
    scheduler = AsyncIOScheduler()
    tasks = _load_tasks()

    for task in tasks:
        cron_expr = task["cron"]
        trigger = CronTrigger.from_crontab(cron_expr)
        scheduler.add_job(
            lambda t=task: anyio.from_thread.run(_run_task, t),
            trigger=trigger,
            id=task["name"],
            replace_existing=True,
        )
        log.info("scheduler: registered task %s [%s]", task["name"], cron_expr)

    scheduler.start()
    return scheduler
