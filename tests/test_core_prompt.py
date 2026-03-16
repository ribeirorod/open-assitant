# tests/test_core_prompt.py


def test_system_prompt_has_scheduled_job_guard():
    """Scheduler prompts use 'DO NOT write to memory' — agent must obey."""
    from src.agent.core import SYSTEM_PROMPT
    assert "DO NOT write to memory" in SYSTEM_PROMPT


def test_system_prompt_has_ambiguity_guardrail():
    from src.agent.core import SYSTEM_PROMPT
    assert "ambiguous" in SYSTEM_PROMPT


def test_system_prompt_has_confirmation_guardrail():
    from src.agent.core import SYSTEM_PROMPT
    assert "confirm" in SYSTEM_PROMPT.lower()


def test_system_prompt_references_skill_tool():
    from src.agent.core import SYSTEM_PROMPT
    assert "Skill" in SYSTEM_PROMPT


def test_system_prompt_has_no_tool_documentation():
    """SYSTEM_PROMPT must not embed gws command references."""
    from src.agent.core import SYSTEM_PROMPT
    assert "gws" not in SYSTEM_PROMPT
