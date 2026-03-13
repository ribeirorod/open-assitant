"""File-backed session store mapping chat IDs → Claude session IDs.

The Claude Agent SDK persists full conversation transcripts internally
(~/.claude/projects/). We only need to store the session_id so we can
pass ``resume=session_id`` on subsequent calls.
"""

from __future__ import annotations

import json
import pathlib
from typing import Any

_STORE_DIR = pathlib.Path.home() / ".open-assistant" / "sessions"


def _safe_filename(chat_id: str) -> str:
    """Sanitise chat_id for use as a filename."""
    return chat_id.replace("/", "_").replace(":", "_").replace(" ", "_")


def _path_for(chat_id: str) -> pathlib.Path:
    _STORE_DIR.mkdir(parents=True, exist_ok=True)
    return _STORE_DIR / f"{_safe_filename(chat_id)}.json"


def load_session(chat_id: str) -> dict[str, Any] | None:
    p = _path_for(chat_id)
    if p.exists():
        try:
            return json.loads(p.read_text())
        except (json.JSONDecodeError, OSError):
            return None
    return None


def save_session(chat_id: str, data: dict[str, Any]) -> None:
    _path_for(chat_id).write_text(json.dumps(data, default=str))


def clear_session(chat_id: str) -> None:
    p = _path_for(chat_id)
    p.unlink(missing_ok=True)
