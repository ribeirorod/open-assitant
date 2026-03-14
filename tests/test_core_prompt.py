# tests/test_core_prompt.py


def test_system_prompt_has_memory_instructions():
    from src.agent.core import SYSTEM_PROMPT
    assert "~/.open-assistant/memory/" in SYSTEM_PROMPT
    assert "start of every response" in SYSTEM_PROMPT
    assert "read index.md" in SYSTEM_PROMPT.lower()
    assert "Write tool" in SYSTEM_PROMPT


def test_system_prompt_limits_daily_tasks():
    from src.agent.core import SYSTEM_PROMPT
    assert "3 meaningful priorities" in SYSTEM_PROMPT


def test_system_prompt_has_procrastination_protocol():
    from src.agent.core import SYSTEM_PROMPT
    assert "procrastinat" in SYSTEM_PROMPT.lower()


def test_system_prompt_scheduled_jobs_must_not_write():
    """Both the meta-instruction and the obeyed string must be present."""
    from src.agent.core import SYSTEM_PROMPT
    assert "Scheduled job prompts will say" in SYSTEM_PROMPT
    assert "DO NOT write to memory" in SYSTEM_PROMPT
