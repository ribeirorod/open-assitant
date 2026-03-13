"""Outbound Telegram notifications for the scheduler.

Uses httpx directly (instead of python-telegram-bot) so we can send messages
without needing the full Application lifecycle.
"""

from __future__ import annotations

import logging

import httpx

from src.config import settings

log = logging.getLogger(__name__)


async def send_telegram_message(chat_id: str, text: str) -> None:
    """Send a text message to a Telegram chat via the Bot API."""
    if not settings.telegram_bot_token:
        log.warning("Cannot send Telegram notification — no bot token configured.")
        return

    url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage"
    # Split long messages
    for i in range(0, len(text), 4096):
        payload = {"chat_id": chat_id, "text": text[i : i + 4096]}
        async with httpx.AsyncClient() as client:
            resp = await client.post(url, json=payload)
            if resp.status_code >= 400:
                log.error("Telegram send failed: %s %s", resp.status_code, resp.text)
