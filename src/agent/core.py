"""Core agent powered by Claude Agent SDK with Google Workspace CLI tools.

Provides session-persistent conversations: each chat_id (Telegram or WhatsApp)
gets its own long-running Claude session that auto-compacts as context grows.
The SDK's ``resume=session_id`` restores full context from prior turns, and
auto-compact transparently summarises older history when context grows large.
"""

from __future__ import annotations

import logging

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ResultMessage,
    TextBlock,
    query,
)

from src.agent.session_store import load_session, save_session
from src.config import settings

log = logging.getLogger(__name__)

SYSTEM_PROMPT = """\
You are Open Assistant — a personal Google Workspace helper that talks to users
over Telegram and WhatsApp.

You have access to the `gws` CLI (Google Workspace CLI) via the Bash tool.
Use it to interact with the user's Google Workspace: Gmail, Calendar, Drive,
Sheets, Docs, Tasks, and more.

Quick reference for the gws CLI:
  gws gmail +send --to <email> --subject <subj> --body <body>
  gws gmail +triage
  gws calendar +agenda
  gws calendar events insert --params '{"calendarId":"primary","requestBody":{"summary":"...","start":{"dateTime":"..."},"end":{"dateTime":"..."}}}'
  gws drive files list --params '{"pageSize":10}'
  gws drive +upload --file <path>
  gws sheets +append --spreadsheet <id> --values "A,B,C"
  gws tasks tasklists list
  gws tasks tasks list --params '{"tasklist":"<id>"}'

Guidelines:
- Always confirm destructive actions (deleting files, sending emails) before executing.
- Format responses for messaging — keep them concise, use line breaks for readability.
- When listing items, use numbered lists or bullet points.
- For scheduled task results, provide a brief summary.
"""


def _build_options(session_id: str | None = None) -> ClaudeAgentOptions:
    opts = ClaudeAgentOptions(
        system_prompt=SYSTEM_PROMPT,
        allowed_tools=["Bash", "Read", "Write"],
        model=settings.claude_model,
        max_turns=25,
    )
    if session_id:
        opts.resume = session_id
    return opts


async def ask_agent(user_message: str, chat_id: str) -> str:
    """Send *user_message* to the Claude agent and return the text response.

    Each ``chat_id`` maps to an independent Claude session.  On the first
    message a new session is created; subsequent messages resume the same
    session via ``resume=session_id``.  The SDK's built-in auto-compact
    transparently summarises older history when context approaches its limit.
    """
    log.info("agent request chat_id=%s msg=%s", chat_id, user_message[:80])

    # Look up an existing session for this chat
    session_data = load_session(chat_id)
    existing_session_id = session_data.get("session_id") if session_data else None

    if existing_session_id:
        log.info("resuming session %s for chat %s", existing_session_id, chat_id)

    options = _build_options(session_id=existing_session_id)

    parts: list[str] = []
    new_session_id: str | None = None

    async for message in query(prompt=user_message, options=options):
        if isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, TextBlock):
                    parts.append(block.text)
        elif isinstance(message, ResultMessage):
            # Capture the session ID so we can resume next time
            new_session_id = getattr(message, "session_id", None)

    # Persist the session mapping
    if new_session_id:
        save_session(chat_id, {"session_id": new_session_id})
        log.info("saved session %s for chat %s", new_session_id, chat_id)

    response = "\n".join(parts).strip() or "(no response)"
    log.info("agent response chat_id=%s len=%d", chat_id, len(response))
    return response
