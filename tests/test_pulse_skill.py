# tests/test_pulse_skill.py
"""Structural tests for the pulse skill (SKILL.md).

The pulse skill is LLM instructions, not Python code. These tests verify that
the skill document contains the key directives added for email reply detection
and calendar update checking.
"""
import pathlib

SKILL_PATH = pathlib.Path(__file__).parent.parent / ".claude" / "skills" / "pulse" / "SKILL.md"


def _content() -> str:
    assert SKILL_PATH.exists(), f"Pulse skill not found at {SKILL_PATH}"
    return SKILL_PATH.read_text()


def test_pulse_skill_exists():
    assert SKILL_PATH.exists()


# --- Reply detection ---

def test_skill_instructs_to_capture_thread_id():
    """Step 3 must instruct capturing threadId per inbox message."""
    assert "threadId" in _content()


def test_skill_instructs_thread_fetch():
    """A step must fetch the full thread via threads get to check for SENT label."""
    content = _content()
    assert "threads get" in content


def test_skill_defines_reply_to_sent_marker():
    """REPLY_TO_SENT must be defined as a classification that bypasses normal filters."""
    assert "REPLY_TO_SENT" in _content()


def test_skill_always_notifies_reply_to_sent():
    """Replies to agent-sent threads must always notify regardless of other filters."""
    content = _content()
    assert "ALWAYS NOTIFY" in content
    # The ALWAYS NOTIFY section must mention REPLY_TO_SENT
    always_notify_block = content[content.index("ALWAYS NOTIFY"):]
    assert "REPLY_TO_SENT" in always_notify_block


def test_skill_output_includes_reply_prefix():
    """Return format must include [REPLY] prefix for reply notifications."""
    assert "[REPLY]" in _content()


# --- Calendar update detection ---

def test_skill_queries_calendar_with_updated_min():
    """Calendar query must use updatedMin to fetch events updated since last run."""
    assert "updatedMin" in _content()


def test_skill_requests_deleted_events():
    """Calendar query must include showDeleted to catch cancellations."""
    assert "showDeleted" in _content()


def test_skill_classifies_cancelled_events():
    """Skill must handle CANCELLED event status."""
    assert "CANCELLED" in _content()


def test_skill_classifies_rsvp_updates():
    """Skill must handle attendee RSVP responses."""
    content = _content()
    assert "RSVP" in content
    assert "responseStatus" in content


def test_skill_output_includes_calendar_prefix():
    """Return format must include [CALENDAR] prefix for calendar notifications."""
    assert "[CALENDAR]" in _content()


def test_skill_emits_iso_timestamp_for_calendar():
    """Step 1 must produce an ISO timestamp (not just Unix epoch) for the calendar query."""
    content = _content()
    # The skill should output both Unix epoch and ISO timestamp
    assert "isoformat" in content


# --- Log format ---

def test_pulse_log_includes_calendar_section():
    """pulse-log.md write template must include a CALENDAR section."""
    content = _content()
    assert "CALENDAR" in content
    assert "REPLY:" in content


# --- Constraints preserved ---

def test_skill_still_constrains_memory_writes():
    """Original constraint — only write pulse-log.md — must still be present."""
    assert "pulse-log.md" in _content()


def test_skill_still_suppresses_empty_output():
    """Skill must still produce no output when nothing is notable."""
    assert "produce no output at all" in _content()
