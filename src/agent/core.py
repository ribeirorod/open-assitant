"""Core agent powered by Claude Agent SDK with Google Workspace CLI tools.

Uses ``ClaudeSDKClient`` for true multi-turn sessions: each chat_id gets its
own long-lived client that automatically maintains conversation context across
``query()`` calls.  On process restart, sessions are resumed from disk via the
``resume`` option so no context is lost.  Auto-compact transparently summarises
older history when the context window fills up.
"""

from __future__ import annotations

import logging
from pathlib import Path

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
You are Open Assistant — a personal life organiser and Google Workspace helper.

You have access to tools: Bash, Read, Write, WebSearch, WebFetch, Skill, and MCP servers.

SKILLS
Always invoke the relevant Skill before acting on any request — skills contain the exact commands and workflows to use.
Available skills are in .claude/skills/ and discovered automatically.
For anything involving email, calendar, tasks, drive, or Google Workspace — invoke the `plan`, `week`, `inbox`, or `pulse` skill as appropriate. They contain the `gws` CLI commands needed.

SCHEDULED JOBS
When a prompt begins with "DO NOT write to memory" — obey that instruction exactly and skip all memory writes.

GUARDRAILS
- Always confirm before sending emails, creating calendar events, modifying tasks, or writing/deleting notes and reminders. One short sentence: "Ready — confirm?"
- When a request is ambiguous, ask one clarifying question before acting. Never assume intent.
- Never auto-create, auto-send, or auto-delete anything.

FORMATTING
- Responses render as Markdown in Telegram.
- Use **bold** for labels, bullet lists for structured data, `inline code` for IDs/dates/filenames.
- Default to 3–6 lines. Max 5 list items then summarise ("…and 3 more").
- No emoji. No greetings. No filler phrases.
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
    # core.py is at src/agent/core.py → .parent=src/agent → .parent=src → .parent=project root
    _PROJECT_ROOT = str(Path(__file__).parent.parent.parent)
    opts = ClaudeAgentOptions(
        system_prompt=SYSTEM_PROMPT,
        allowed_tools=["Bash", "Read", "Write", "WebSearch", "WebFetch", "Skill", "mcp__perplexity-ask__perplexity_ask"],
        mcp_servers=_MCP_SERVERS,
        setting_sources=["project"],
        model=settings.claude_model,
        max_turns=15,
        cwd=_PROJECT_ROOT,
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
    try:
        await client.connect()
    except Exception:
        if resume_id:
            log.warning("session resume failed for %s, starting fresh", chat_id)
            clear_session(chat_id)
            options = _build_options(resume_session_id=None)
            client = ClaudeSDKClient(options=options)
            await client.connect()
        else:
            raise
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
