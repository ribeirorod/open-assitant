# tests/test_telegram_commands.py
import os
import pytest
from unittest.mock import patch


@pytest.fixture
def tg_app():
    """Build the Telegram app with a fake token."""
    with patch.dict(os.environ, {"OA_TELEGRAM_BOT_TOKEN": "1234567890:FAKE_TOKEN_FOR_TESTING"}):
        import importlib
        import src.config as cfg
        importlib.reload(cfg)
        cfg.settings.telegram_bot_token = "1234567890:FAKE_TOKEN_FOR_TESTING"

        from src.channels.telegram import build_telegram_app
        app = build_telegram_app()
        return app


def _registered_commands(app) -> set[str]:
    from telegram.ext import CommandHandler
    commands = set()
    for group_handlers in app.handlers.values():
        for h in group_handlers:
            if isinstance(h, CommandHandler):
                commands.update(h.commands)
    return commands


def test_original_commands_still_registered(tg_app):
    cmds = _registered_commands(tg_app)
    assert "start" in cmds
    assert "reset" in cmds


def test_new_commands_registered(tg_app):
    cmds = _registered_commands(tg_app)
    for cmd in ["plan", "week", "note", "avoid", "update", "chatid"]:
        assert cmd in cmds, f"/{cmd} not registered"
