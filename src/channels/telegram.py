"""Telegram bot channel adapter using python-telegram-bot."""

from __future__ import annotations

import asyncio
import base64
import logging

import anthropic
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
from src.config import settings

log = logging.getLogger(__name__)

MAX_TG_MESSAGE_LENGTH = 4090  # slight buffer under the 4096 hard limit

_anthropic = anthropic.AsyncAnthropic()


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
    await _send_markdown(update, response)


async def _chatid(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Return the user's Telegram chat ID — needed to configure schedules.yaml."""
    if not _is_allowed(update):
        return
    await update.message.reply_text(f"Your chat ID: `{update.effective_chat.id}`", parse_mode="MarkdownV2")


# ── Life-assistant commands ──────────────────────────────────────────────────

_PLAN_PROMPT = """\
/plan — run the daily planning workflow:
1. Read ~/.open-assistant/memory/index.md then projects.md, commitments.md, preferences.md, procrastination.md.
2. Run: gws calendar +agenda
3. Run: gws gmail +triage
4. Run: gws tasks tasks list --params '{"tasklist":"@default"}'
5. Produce a structured daily plan:
   **Today's 3 priorities** (realistic given the calendar — no more than 3, bold them)
   **Emails needing action** (max 3, one line each with suggested next step)
   **One item to face today** (oldest item in procrastination.md by added date, if any >3 days old)
6. Ask: "Does this look right?"
Max 15 lines. Do NOT write to memory during this scheduled prompt."""


_WEEK_PROMPT = """\
/week — run the weekly overview workflow:
1. Read all files in ~/.open-assistant/memory/.
2. Use Bash to compute next Monday and Sunday in Europe/Berlin time:
   python3 -c "from datetime import datetime, timedelta; import zoneinfo; tz=zoneinfo.ZoneInfo('Europe/Berlin'); now=datetime.now(tz); offset=now.strftime('%z'); offset=offset[:3]+':'+offset[3:]; today=now.date(); monday=today+timedelta(days=(7-today.weekday())%7 or 7); sunday=monday+timedelta(days=6); print(monday.isoformat()+'T00:00:00'+offset, sunday.isoformat()+'T23:59:59'+offset)"
3. Run: gws calendar events list --params '{"calendarId":"primary","timeMin":"<MONDAY>","timeMax":"<SUNDAY>","singleEvents":true,"orderBy":"startTime"}'
4. Run: gws tasks tasks list --params '{"tasklist":"@default"}'
5. Output:
   - Days that look overloaded (>3 commitments)
   - Missing time blocks for: gym (need 3 sessions), family/relationship, piano
   - Suggested time blocks (list only — do NOT create calendar events)
   - One thing to defer if the week is too full
6. Ask: "Want me to create these blocks?" — only create after explicit confirmation."""


_AVOID_PROMPT = """\
/avoid — surface procrastinated items:
1. Read ~/.open-assistant/memory/procrastination.md.
2. Run: gws tasks tasks list --params '{"tasklist":"@default"}' to find tasks with old due dates.
3. List avoided items by name with days elapsed (calculate from [YYYY-MM-DD added] in procrastination.md).
4. Ask: "Which one can you do 30 minutes on today?"
5. When user picks one:
   a. Compute current time in Berlin: python3 -c "from datetime import datetime; import zoneinfo; tz=zoneinfo.ZoneInfo('Europe/Berlin'); now=datetime.now(tz); print(now.strftime('%H:%M'), now.isoformat())"
   b. Run: gws calendar events list --params '{"calendarId":"primary","timeMin":"<NOW_ISO>","timeMax":"<END_OF_DAY_ISO>","singleEvents":true,"orderBy":"startTime"}' to find free slots.
   c. Identify first gap of ≥30 minutes. If none found or parsing unclear, ask: "What time works for you?"
   d. Propose: "I can block HH:MM–HH:MM for [item]. Confirm?"
   e. Only create the calendar event after explicit confirmation. Event title: "Focus: [item name]" """


_UPDATE_PROMPT_TEMPLATE = """\
/update {args}— update memory:
1. Read ~/.open-assistant/memory/index.md.
2. Read the memory file most relevant to the topic "{args}".
3. Ask what's changed (if the user hasn't already explained in this message).
4. Write the updated content back to the file using the Write tool.
5. Confirm: "Updated [filename] — here's what changed: ..."."""


async def _plan(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await _dispatch(update, _PLAN_PROMPT)


async def _week(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await _dispatch(update, _WEEK_PROMPT)


async def _note(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    args = " ".join(ctx.args) if ctx.args else ""
    if not args:
        await update.message.reply_text("Usage: /note [your note text]")
        return
    prompt = (
        f"/note — capture this: {args}\n\n"
        "Determine whether this belongs in Google Tasks, a memory file, or both.\n"
        "- If it is a task or reminder: add it to Google Tasks under the right project label.\n"
        "- If it is a goal, preference, or personal fact: write it to the appropriate memory file.\n"
        "- If both apply: do both.\n"
        "Confirm exactly what you stored and where."
    )
    await _dispatch(update, prompt)


async def _avoid(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await _dispatch(update, _AVOID_PROMPT)


async def _update(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    args = " ".join(ctx.args) if ctx.args else ""
    await _dispatch(update, _UPDATE_PROMPT_TEMPLATE.format(args=f"'{args}' " if args else ""))


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


async def _transcribe_voice(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> str | None:
    """Download a Telegram voice/audio message and transcribe it via Claude."""
    msg = update.message
    voice = msg.voice or msg.audio
    if not voice:
        return None

    tg_file = await ctx.bot.get_file(voice.file_id)
    audio_bytes = await tg_file.download_as_bytearray()
    audio_b64 = base64.standard_b64encode(bytes(audio_bytes)).decode()

    media_type = "audio/ogg" if msg.voice else "audio/mpeg"

    result = await _anthropic.messages.create(
        model="claude-opus-4-6",
        max_tokens=1024,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "document",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": audio_b64,
                        },
                    },
                    {
                        "type": "text",
                        "text": "Transcribe this audio message exactly as spoken. Return only the transcript, no commentary.",
                    },
                ],
            }
        ],
    )
    return result.content[0].text.strip() if result.content else None


async def _handle_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    log.info("message from @%s: allowed=%s", getattr(update.effective_user, "username", "?"), _is_allowed(update))
    if not _is_allowed(update):
        return

    chat_id = str(update.effective_chat.id)
    text = update.message.text or ""
    if not text.strip():
        return

    stop = asyncio.Event()
    typing_task = asyncio.create_task(_keep_typing(update, stop))
    try:
        response = await ask_agent(text, chat_id)
    finally:
        stop.set()
        typing_task.cancel()

    await _send_markdown(update, response)


async def _handle_voice(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle voice notes and audio files: transcribe then forward to agent."""
    if not _is_allowed(update):
        return

    chat_id = str(update.effective_chat.id)

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

    await update.message.reply_text(f'Heard: "{transcript}"')

    try:
        response = await ask_agent(transcript, chat_id)
    finally:
        stop.set()
        typing_task.cancel()

    await _send_markdown(update, response)


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
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, _handle_message))
    app.add_handler(MessageHandler(filters.VOICE | filters.AUDIO, _handle_voice))
    app.add_error_handler(_handle_error)
    return app
