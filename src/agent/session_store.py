"""Simple file-backed session store for mapping chat IDs to conversation context."""

from __future__ import annotations

import json
import pathlib
from typing import Any

_STORE_DIR = pathlib.Path.home() / ".open-assistant" / "sessions"


def _path_for(chat_id: str) -> pathlib.Path:
    _STORE_DIR.mkdir(parents=True, exist_ok=True)
    return _STORE_DIR / f"{chat_id}.json"


def load_session(chat_id: str) -> dict[str, Any] | None:
    p = _path_for(chat_id)
    if p.exists():
        return json.loads(p.read_text())
    return None


def save_session(chat_id: str, data: dict[str, Any]) -> None:
    _path_for(chat_id).write_text(json.dumps(data, default=str))


def clear_session(chat_id: str) -> None:
    p = _path_for(chat_id)
    p.unlink(missing_ok=True)
