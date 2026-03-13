"""Core agent powered by Claude Agent SDK with Google Workspace CLI tools.

Provides session-persistent conversations: each chat_id (Telegram or WhatsApp)
gets its own long-running Claude session that auto-compacts as context grows.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    TextBlock,
    query,
)

from src.config import settings

if TYPE_CHECKING:
    pass

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


def _build_options() -> ClaudeAgentOptions:
    return ClaudeAgentOptions(
        system_prompt=SYSTEM_PROMPT,
        allowed_tools=["Bash", "Read", "Write"],
        model=settings.claude_model,
        max_turns=25,
    )


async def ask_agent(user_message: str, chat_id: str) -> str:
    """Send *user_message* to the Claude agent and return the text response.

    Each ``chat_id`` maps to an independent session.  The Claude Agent SDK
    handles auto-compact internally so long conversations stay within the
    context window.
    """
    log.info("agent request chat_id=%s msg=%s", chat_id, user_message[:80])

    options = _build_options()

    # Prefix prompt with session hint so the agent can keep track of who it's
    # talking to across turns.  The SDK's built-in session / auto-compact
    # takes care of trimming history when the context grows.
    prompt = f"[session:{chat_id}] {user_message}"

    parts: list[str] = []
    async for message in query(prompt=prompt, options=options):
        if isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, TextBlock):
                    parts.append(block.text)

    response = "\n".join(parts).strip() or "(no response)"
    log.info("agent response chat_id=%s len=%d", chat_id, len(response))
    return response
