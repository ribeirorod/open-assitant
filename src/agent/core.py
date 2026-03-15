"""Core agent powered by Claude Agent SDK with Google Workspace CLI tools.

Uses ``ClaudeSDKClient`` for true multi-turn sessions: each chat_id gets its
own long-lived client that automatically maintains conversation context across
``query()`` calls.  On process restart, sessions are resumed from disk via the
``resume`` option so no context is lost.  Auto-compact transparently summarises
older history when the context window fills up.
"""

from __future__ import annotations

import logging

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ClaudeSDKClient,
    ResultMessage,
    SystemMessage,
    TextBlock,
)
from claude_agent_sdk.types import McpStdioServerConfig

from src.agent.session_store import clear_session, load_session, save_session
from src.config import settings

log = logging.getLogger(__name__)

SYSTEM_PROMPT = """\
You are Open Assistant — a personal Google Workspace helper and life organiser running on Telegram.

You have access to the `gws` CLI via the Bash tool for Gmail, Calendar, Drive, Sheets, Docs, and Tasks.

Quick reference:
  gws gmail +send --to <email> --subject <subj> --body <body>
  gws gmail +triage
  gws calendar +agenda
  gws calendar events insert --params '{"calendarId":"primary","requestBody":{"summary":"...","start":{"dateTime":"..."},"end":{"dateTime":"..."}}}'
  gws calendar events list --params '{"calendarId":"primary","timeMin":"<RFC3339>","timeMax":"<RFC3339>","singleEvents":true,"orderBy":"startTime"}'
  gws drive files list --params '{"pageSize":10}'
  gws tasks tasks list --params '{"tasklist":"<id>"}'
  gws tasks tasks list --params '{"tasklist":"@default"}'

MEMORY — your persistent knowledge base lives at ~/.open-assistant/memory/:
- At the start of every response, read index.md with the Read tool.
- Then read whichever topic files are relevant to the current request (see index.md for the list).
- When you learn something new (project update, deadline, preference, avoidance pattern), update the
  relevant memory file immediately with the Write tool. Overwrite the whole file — Read it first,
  then Write the updated version.
- If a topic has no existing file, create one and add a one-line entry to index.md.
- Procrastination entries must use this format: "- [YYYY-MM-DD added] Item description"
  so age in days can be calculated.
- Scheduled job prompts will say "DO NOT write to memory" — obey that instruction.

PLANNING DISCIPLINE:
- When planning a day or week, propose at most 3 meaningful priorities. If the user lists more,
  flag it: "That's more than 3 — which would you drop?"
- Protect time for gym (min 3 sessions/week), family, and piano practice when scheduling.

PROCRASTINATION PROTOCOL:
- Surface items from procrastination.md that are older than 3 days in every /plan and morning briefing.
- If an item keeps appearing across multiple sessions without progress, name it directly:
  "You've been avoiding [X] for N days. What's actually blocking you?"

CONFIRMATION BEFORE ACTION:
- Always confirm before sending emails, creating calendar events, or modifying/deleting tasks.
  One short sentence is enough: "Ready to send — confirm?"
- Never auto-create or auto-send anything.

FORMATTING — responses are rendered as Markdown in Telegram:
- Use **bold** for labels and headings, not decorative emphasis.
- Use bullet lists or numbered lists for structured data.
- Use `inline code` for values like dates, IDs, file names.
- Use --- to visually separate distinct sections.
- Never use emoji or emoticons.
- Never start with a greeting or sign off at the end.
- No filler phrases ("Sure!", "Of course!", "Great question!", "Let me help you with that").

BREVITY:
- Default to 3–6 lines. Only go longer if the data genuinely requires it.
- For lists, show max 5 items then summarise ("…and 3 more").
"""

# ── Client pool ─────────────────────────────────────────────────────────────
# One ClaudeSDKClient per chat_id, kept alive for the lifetime of the process.
# This gives true multi-turn: each `client.query()` automatically continues the
# same session with full prior context.

_clients: dict[str, ClaudeSDKClient] = {}


_MCP_SERVERS: dict[str, McpStdioServerConfig] = {
    "perplexity-ask": McpStdioServerConfig(
        command="npx",
        args=["-y", "server-perplexity-ask"],
        env={"PERPLEXITY_API_KEY": settings.perplexity_api_key},
    ),
}


def _build_options(resume_session_id: str | None = None) -> ClaudeAgentOptions:
    opts = ClaudeAgentOptions(
        system_prompt=SYSTEM_PROMPT,
        allowed_tools=["Bash", "Read", "Write", "WebSearch", "WebFetch", "Skill", "mcp__perplexity-ask__perplexity_ask"],
        mcp_servers=_MCP_SERVERS,
        setting_sources=["project"],
        model=settings.claude_model,
        max_turns=15,
    )
    if resume_session_id:
        opts.resume = resume_session_id
    return opts


async def _get_or_create_client(chat_id: str) -> ClaudeSDKClient:
    """Return an existing client for *chat_id*, or create (and connect) one.

    On first contact after a process restart, the stored session_id is used to
    resume the prior conversation so the agent picks up where it left off.
    """
    if chat_id in _clients:
        return _clients[chat_id]

    # Check for a persisted session from a prior process lifetime
    session_data = load_session(chat_id)
    resume_id = session_data.get("session_id") if session_data else None

    if resume_id:
        log.info("resuming prior session %s for chat %s", resume_id, chat_id)

    options = _build_options(resume_session_id=resume_id)
    client = ClaudeSDKClient(options=options)
    await client.connect()
    _clients[chat_id] = client
    return client


def _extract_text(message: object) -> str | None:
    """Pull readable text from an AssistantMessage."""
    if isinstance(message, AssistantMessage):
        pieces = []
        for block in message.content:
            if isinstance(block, TextBlock):
                pieces.append(block.text)
        return "\n".join(pieces) if pieces else None
    return None


async def ask_agent(user_message: str, chat_id: str) -> str:
    """Send *user_message* to the Claude agent and return the text response.

    Each ``chat_id`` maps to its own ``ClaudeSDKClient``.  Within a process
    lifetime, subsequent calls automatically continue the same session (the
    client tracks it internally).  Across restarts, the session is resumed
    from disk via ``resume=session_id``.
    """
    log.info("agent request chat_id=%s msg=%s", chat_id, user_message[:80])

    client = await _get_or_create_client(chat_id)
    await client.query(user_message)

    parts: list[str] = []
    session_id: str | None = None

    async for message in client.receive_response():
        text = _extract_text(message)
        if text:
            parts.append(text)

        # Capture session_id from the init SystemMessage or ResultMessage
        if isinstance(message, SystemMessage):
            sid = getattr(message, "session_id", None)
            if sid:
                session_id = sid
        elif isinstance(message, ResultMessage):
            sid = getattr(message, "session_id", None)
            if sid:
                session_id = sid

    # Persist session mapping for cross-restart resume
    if session_id:
        save_session(chat_id, {"session_id": session_id})

    response = "\n".join(parts).strip() or "(no response)"
    log.info("agent response chat_id=%s len=%d", chat_id, len(response))
    return response


async def reset_agent(chat_id: str) -> None:
    """Tear down the client for *chat_id* and remove persisted session."""
    client = _clients.pop(chat_id, None)
    if client:
        try:
            await client.disconnect()
        except Exception:
            log.debug("disconnect error for chat %s (ignored)", chat_id, exc_info=True)
    clear_session(chat_id)
    log.info("session reset for chat %s", chat_id)


async def shutdown_all() -> None:
    """Gracefully disconnect all active clients (call on app shutdown)."""
    for chat_id, client in list(_clients.items()):
        try:
            await client.disconnect()
        except Exception:
            log.debug("disconnect error for chat %s", chat_id, exc_info=True)
    _clients.clear()
