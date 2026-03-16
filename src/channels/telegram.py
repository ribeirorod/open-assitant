"""Telegram bot channel adapter using python-telegram-bot."""

from __future__ import annotations

import asyncio
import logging
import pathlib
from datetime import datetime, timezone

# telegram.py is at src/channels/telegram.py
# .parent → src/channels  .parent → src  .parent → project root
_SKILLS_DIR = pathlib.Path(__file__).parent.parent.parent / ".claude" / "skills"


def _skill(name: str, **kwargs: str) -> str:
    """Load a skill from .claude/skills/<name>/SKILL.md.

    User args are appended as a suffix — never injected via str.format(),
    because SKILL.md files contain JSON with curly braces that would crash it.
    """
    text = (_SKILLS_DIR / name / "SKILL.md").read_text()
    if kwargs.get("args"):
        text = text + f"\n\nUser input: {kwargs['args']}"
    return text

import groq
import httpx
import openai
from telegramify_markdown import markdownify
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from src.agent.core import ask_agent, reset_agent
from src.agent.session_store import load_session, save_session
from src.config import settings

log = logging.getLogger(__name__)

MAX_TG_MESSAGE_LENGTH = 4090  # slight buffer under the 4096 hard limit
MISSED_MESSAGE_THRESHOLD = 300  # seconds — messages older than this at receive time are "missed"

_groq = groq.AsyncGroq(api_key=settings.groq_api_key) if settings.groq_api_key else None
_openai = openai.AsyncOpenAI(api_key=settings.openai_api_key) if settings.openai_api_key else None


def _is_missed_message(update: Update) -> bool:
    """Return True if the message arrived while the bot was likely offline."""
    msg = update.message
    if msg is None or msg.date is None:
        return False
    age = datetime.now(timezone.utc) - msg.date
    return age.total_seconds() > MISSED_MESSAGE_THRESHOLD


def _record_reply(chat_id: str, message_id: int) -> None:
    """Persist the ID of the last message the bot replied to."""
    data = load_session(chat_id) or {}
    data["last_replied_message_id"] = message_id
    save_session(chat_id, data)


def _is_allowed(update: Update) -> bool:
    if not settings.telegram_allowed_users:
        return True
    username = update.effective_user.username if update.effective_user else None
    if not username:
        return False
    return username in settings.telegram_allowed_users or f"@{username}" in settings.telegram_allowed_users


def _split_mdv2(text: str, max_len: int = MAX_TG_MESSAGE_LENGTH) -> list[str]:
    """Split a MarkdownV2 string at paragraph or line boundaries."""
    if len(text) <= max_len:
        return [text]
    chunks: list[str] = []
    while text:
        if len(text) <= max_len:
            chunks.append(text)
            break
        cut = text.rfind("\n\n", 0, max_len)
        if cut == -1:
            cut = text.rfind("\n", 0, max_len)
        if cut == -1:
            cut = max_len
        chunks.append(text[:cut])
        text = text[cut:].lstrip()
    return chunks


async def _send_markdown(update: Update, markdown: str) -> None:
    """Convert markdown to MarkdownV2 and send in logical chunks."""
    mdv2 = markdownify(markdown)
    for chunk in _split_mdv2(mdv2):
        await update.message.reply_text(chunk, parse_mode="MarkdownV2")


async def _keep_typing(update: Update, stop: asyncio.Event) -> None:
    """Pulse the typing indicator every 4 s until *stop* is set."""
    while not stop.is_set():
        try:
            await update.effective_chat.send_action("typing")
        except Exception:
            pass
        await asyncio.sleep(4)


async def _dispatch(update: Update, prompt: str) -> None:
    """Route any prompt through the agent with typing indicator."""
    if not _is_allowed(update):
        return
    chat_id = str(update.effective_chat.id)
    stop = asyncio.Event()
    typing_task = asyncio.create_task(_keep_typing(update, stop))
    try:
        response = await ask_agent(prompt, chat_id)
    finally:
        stop.set()
        typing_task.cancel()
        try:
            await typing_task
        except asyncio.CancelledError:
            pass
    await _send_markdown(update, response)
    if update.message:
        _record_reply(chat_id, update.message.message_id)


async def _chatid(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Return the user's Telegram chat ID — needed to configure schedules.yaml."""
    if not _is_allowed(update):
        return
    await update.message.reply_text(f"Your chat ID: {update.effective_chat.id}")


# ── Life-assistant commands ──────────────────────────────────────────────────

async def _plan(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await _dispatch(update, _skill("plan"))


async def _week(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await _dispatch(update, _skill("week"))


async def _note(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    args = " ".join(ctx.args) if ctx.args else ""
    if not args:
        await update.message.reply_text("Usage: /note [your note text]")
        return
    await _dispatch(update, _skill("note", args=args))


async def _avoid(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await _dispatch(update, _skill("avoid"))


async def _update(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    args = " ".join(ctx.args) if ctx.args else ""
    if not args:
        await update.message.reply_text("Usage: /update [topic]  e.g. /update projects")
        return
    await _dispatch(update, _skill("update", args=args))


async def _calibration(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await _dispatch(update, _skill("calibration"))


async def _memory(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    args = " ".join(ctx.args) if ctx.args else ""
    await _dispatch(update, _skill("memory") + (f"\n\nSubcommand: {args}" if args else ""))


async def _project(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    args = " ".join(ctx.args) if ctx.args else ""
    await _dispatch(update, _skill("project") + (f"\n\nProject name: {args}" if args else ""))


async def _find(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    args = " ".join(ctx.args) if ctx.args else ""
    if not args:
        await update.message.reply_text("Usage: /find <filename or keyword>")
        return
    await _dispatch(update, _skill("find", args=args))


async def _inbox(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await _dispatch(update, _skill("inbox"))


async def _start(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_allowed(update):
        return
    await update.message.reply_text(
        "Google Workspace assistant ready.\n"
        "Send a message or a voice note to get started.\n"
        "Use /reset to clear the session."
    )


async def _reset(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_allowed(update):
        return
    chat_id = str(update.effective_chat.id)
    await reset_agent(chat_id)
    await update.message.reply_text("Session cleared.")


async def _download_file(ctx: ContextTypes.DEFAULT_TYPE, file_id: str) -> bytes:
    """Download a Telegram file by file_id and return its raw bytes."""
    tg_file = await ctx.bot.get_file(file_id)
    return bytes(await tg_file.download_as_bytearray())


async def _transcribe_groq(audio_bytes: bytes, filename: str) -> str | None:
    if _groq is None:
        return None
    result = await _groq.audio.transcriptions.create(
        model="whisper-large-v3-turbo",
        file=(filename, audio_bytes),
        response_format="text",
    )
    return result.strip() if result else None


async def _transcribe_openai(audio_bytes: bytes, filename: str) -> str | None:
    if _openai is None:
        return None
    result = await _openai.audio.transcriptions.create(
        model="whisper-1",
        file=(filename, audio_bytes),
        response_format="text",
    )
    return result.strip() if result else None


async def _transcribe_deepgram(audio_bytes: bytes, filename: str) -> str | None:
    if not settings.deepgram_api_key:
        return None
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://api.deepgram.com/v1/listen?model=nova-2&smart_format=true",
            headers={"Authorization": f"Token {settings.deepgram_api_key}"},
            content=audio_bytes,
            timeout=30,
        )
        resp.raise_for_status()
        transcript = resp.json()["results"]["channels"][0]["alternatives"][0]["transcript"]
        return transcript.strip() if transcript else None


async def _transcribe(audio_bytes: bytes, filename: str) -> str | None:
    """Try STT providers in order: Groq → OpenAI → Deepgram."""
    for provider in (_transcribe_groq, _transcribe_openai, _transcribe_deepgram):
        try:
            result = await provider(audio_bytes, filename)
            if result:
                log.info("STT succeeded via %s", provider.__name__)
                return result
        except Exception as exc:
            log.warning("STT provider %s failed: %s", provider.__name__, exc)
    return None


async def _synthesize(text: str) -> bytes | None:
    """Convert text to speech via OpenAI TTS. Returns OGG bytes or None."""
    if _openai is None:
        return None
    try:
        response = await _openai.audio.speech.create(
            model="tts-1",
            voice="alloy",
            input=text,
            response_format="opus",  # OGG/Opus — native Telegram voice format
        )
        return response.content
    except Exception as exc:
        log.warning("TTS failed: %s", exc)
        return None


async def _transcribe_voice(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> str | None:
    """Download a Telegram voice/audio message and transcribe it via Groq Whisper."""
    msg = update.message
    voice = msg.voice or msg.audio
    if not voice:
        return None

    filename = "voice.ogg" if msg.voice else "audio.mp3"
    audio_bytes = await _download_file(ctx, voice.file_id)
    return await _transcribe(audio_bytes, filename)


async def _handle_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    log.info("message from @%s: allowed=%s", getattr(update.effective_user, "username", "?"), _is_allowed(update))
    if not _is_allowed(update):
        return

    chat_id = str(update.effective_chat.id)
    text = update.message.text or ""
    if not text.strip():
        return

    if _is_missed_message(update):
        snippet = text[:60] + ("…" if len(text) > 60 else "")
        await update.message.reply_text(
            f'I may have missed this while I was offline: "{snippet}"\nDo you still need my help with this?'
        )
        _record_reply(chat_id, update.message.message_id)
        return

    stop = asyncio.Event()
    typing_task = asyncio.create_task(_keep_typing(update, stop))
    try:
        response = await ask_agent(text, chat_id)
    finally:
        stop.set()
        typing_task.cancel()

    await _send_markdown(update, response)
    _record_reply(chat_id, update.message.message_id)


async def _handle_voice(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle voice notes and audio files: transcribe then forward to agent."""
    if not _is_allowed(update):
        return

    chat_id = str(update.effective_chat.id)

    if _is_missed_message(update):
        await update.message.reply_text(
            'I may have missed a voice message while I was offline.\nDo you still need my help with this?'
        )
        _record_reply(chat_id, update.message.message_id)
        return

    stop = asyncio.Event()
    typing_task = asyncio.create_task(_keep_typing(update, stop))
    try:
        transcript = await _transcribe_voice(update, ctx)
    except Exception:
        stop.set()
        typing_task.cancel()
        log.exception("voice transcription failed")
        await update.message.reply_text("Could not transcribe audio.")
        return

    if not transcript:
        stop.set()
        typing_task.cancel()
        await update.message.reply_text("No speech detected in that audio.")
        return

    try:
        response = await ask_agent(transcript, chat_id)
    finally:
        stop.set()
        typing_task.cancel()

    # Try to reply with voice; fall back to text if TTS unavailable or fails
    audio = await _synthesize(response)
    if audio:
        await update.message.reply_voice(audio)
    else:
        await _send_markdown(update, response)
    _record_reply(chat_id, update.message.message_id)


async def _handle_error(update: object, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    log.exception("Telegram handler error", exc_info=ctx.error)
    if isinstance(update, Update) and update.message:
        await update.message.reply_text("Something went wrong. Please try again.")


def build_telegram_app() -> Application:
    """Create and return a configured Telegram Application (not yet running)."""
    if not settings.telegram_bot_token:
        raise RuntimeError("OA_TELEGRAM_BOT_TOKEN is required for the Telegram channel")

    app = Application.builder().token(settings.telegram_bot_token).build()
    app.add_handler(CommandHandler("start", _start))
    app.add_handler(CommandHandler("reset", _reset))
    app.add_handler(CommandHandler("chatid", _chatid))
    app.add_handler(CommandHandler("plan", _plan))
    app.add_handler(CommandHandler("week", _week))
    app.add_handler(CommandHandler("note", _note))
    app.add_handler(CommandHandler("avoid", _avoid))
    app.add_handler(CommandHandler("update", _update))
    app.add_handler(CommandHandler("calibration", _calibration))
    app.add_handler(CommandHandler("memory", _memory))
    app.add_handler(CommandHandler("project", _project))
    app.add_handler(CommandHandler("find", _find))
    app.add_handler(CommandHandler("inbox", _inbox))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, _handle_message))
    app.add_handler(MessageHandler(filters.VOICE | filters.AUDIO, _handle_voice))
    app.add_error_handler(_handle_error)
    return app
