"""Telegram bot channel adapter using python-telegram-bot."""

from __future__ import annotations

import logging

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from src.agent.core import ask_agent
from src.agent.session_store import clear_session
from src.config import settings

log = logging.getLogger(__name__)

MAX_TG_MESSAGE_LENGTH = 4096


def _is_allowed(update: Update) -> bool:
    if not settings.telegram_allowed_users:
        return True
    username = update.effective_user.username if update.effective_user else None
    return username in settings.telegram_allowed_users


async def _start(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_allowed(update):
        return
    await update.message.reply_text(
        "Hey! I'm your Google Workspace assistant.\n"
        "Just send me a message — I can read your mail, manage your calendar, "
        "list Drive files, and more."
    )


async def _reset(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_allowed(update):
        return
    chat_id = str(update.effective_chat.id)
    clear_session(chat_id)
    await update.message.reply_text("Session cleared. Starting fresh!")


async def _handle_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_allowed(update):
        return

    chat_id = str(update.effective_chat.id)
    text = update.message.text or ""
    if not text.strip():
        return

    # Show "typing" indicator while the agent works
    await update.effective_chat.send_action("typing")

    response = await ask_agent(text, chat_id)

    # Telegram has a 4096-char limit per message — split if necessary.
    for i in range(0, len(response), MAX_TG_MESSAGE_LENGTH):
        await update.message.reply_text(response[i : i + MAX_TG_MESSAGE_LENGTH])


def build_telegram_app() -> Application:
    """Create and return a configured Telegram Application (not yet running)."""
    if not settings.telegram_bot_token:
        raise RuntimeError("OA_TELEGRAM_BOT_TOKEN is required for the Telegram channel")

    app = Application.builder().token(settings.telegram_bot_token).build()
    app.add_handler(CommandHandler("start", _start))
    app.add_handler(CommandHandler("reset", _reset))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, _handle_message))
    return app
