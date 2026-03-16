# tests/test_missed_message.py
"""Tests for missed-message detection and reply-recording."""

from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch

import pytest

from src.channels.telegram import (
    MISSED_MESSAGE_THRESHOLD,
    _is_missed_message,
    _record_reply,
)


def _make_update(age_seconds: float) -> MagicMock:
    """Return a mock Update whose message.date is age_seconds old."""
    msg_date = datetime.now(timezone.utc) - timedelta(seconds=age_seconds)
    message = MagicMock()
    message.date = msg_date
    update = MagicMock()
    update.message = message
    return update


def test_fresh_message_not_missed():
    update = _make_update(10)
    assert _is_missed_message(update) is False


def test_old_message_is_missed():
    update = _make_update(MISSED_MESSAGE_THRESHOLD + 60)
    assert _is_missed_message(update) is True


def test_just_below_threshold_not_missed():
    update = _make_update(MISSED_MESSAGE_THRESHOLD - 10)
    assert _is_missed_message(update) is False


def test_no_message_not_missed():
    update = MagicMock()
    update.message = None
    assert _is_missed_message(update) is False


def test_record_reply_saves_to_session(tmp_path):
    """_record_reply persists last_replied_message_id in the session store."""
    with patch("src.channels.telegram.load_session", return_value={"session_id": "abc"}), \
         patch("src.channels.telegram.save_session") as mock_save:
        _record_reply("42", 999)
        mock_save.assert_called_once_with("42", {"session_id": "abc", "last_replied_message_id": 999})


def test_record_reply_creates_new_session_if_none(tmp_path):
    """_record_reply works even when no prior session data exists."""
    with patch("src.channels.telegram.load_session", return_value=None), \
         patch("src.channels.telegram.save_session") as mock_save:
        _record_reply("99", 123)
        mock_save.assert_called_once_with("99", {"last_replied_message_id": 123})
