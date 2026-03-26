"""Application entrypoint — runs Telegram bot + WhatsApp webhook server + scheduler."""

from __future__ import annotations

import asyncio
import contextlib
import logging

import uvicorn
from fastapi import FastAPI

from src.channels.whatsapp import router as whatsapp_router
from src.config import settings
from src.memory.sync import pull as memory_pull
from src.scheduler.scheduler import start_scheduler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s  %(message)s",
)
log = logging.getLogger(__name__)


def _create_api() -> FastAPI:
    app = FastAPI(title="Open Assistant – Webhook Server")
    app.include_router(whatsapp_router)

    @app.get("/health")
    async def health() -> dict:
        return {"status": "ok"}

    return app


async def _run() -> None:
    # 0. Pull latest memory from GDrive before anything else
    try:
        pull_results = await memory_pull()
        if pull_results:
            log.info("startup memory pull: %s", pull_results)
    except Exception:
        log.warning("startup memory pull failed — continuing with local files", exc_info=True)

    # 1. Start the scheduler (cron tasks)
    scheduler = start_scheduler()

    tasks: list[asyncio.Task] = []

    # 2. Start the webhook server (for WhatsApp inbound)
    api = _create_api()
    config = uvicorn.Config(
        api,
        host=settings.webhook_host,
        port=settings.webhook_port,
        log_level="info",
        reload=False,
    )
    server = uvicorn.Server(config)
    tasks.append(asyncio.create_task(server.serve()))

    # 3. Start the Telegram bot (polling)
    if settings.telegram_bot_token:
        from src.channels.telegram import build_telegram_app

        tg_app = build_telegram_app()
        # initialize and start polling in the background
        await tg_app.initialize()
        await tg_app.start()
        await tg_app.updater.start_polling()
        log.info("Telegram bot started (polling)")
    else:
        tg_app = None
        log.warning("No Telegram bot token — Telegram channel disabled.")

    log.info("Open Assistant is running.")

    try:
        await asyncio.gather(*tasks)
    finally:
        # Gracefully tear down all agent sessions
        from src.agent.core import shutdown_all

        await shutdown_all()
        scheduler.shutdown(wait=False)
        if tg_app:
            with contextlib.suppress(Exception):
                await tg_app.updater.stop()
                await tg_app.stop()
                await tg_app.shutdown()


def main() -> None:
    asyncio.run(_run())


if __name__ == "__main__":
    main()
