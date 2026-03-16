# tests/test_skill_loader.py
import pathlib
from unittest.mock import mock_open, patch


def _get_skill_fn():
    """Import _skill from telegram without triggering the full module import."""
    import importlib
    import src.channels.telegram as tg
    importlib.reload(tg)
    return tg._skill, tg._SKILLS_DIR


def test_skills_dir_points_to_claude_skills():
    _, skills_dir = _get_skill_fn()
    assert skills_dir.name == "skills"
    assert skills_dir.parent.name == ".claude"


def test_skill_reads_skill_md(tmp_path):
    """_skill('plan') reads .claude/skills/plan/SKILL.md."""
    fake_content = "# Plan skill content"
    skill_file = tmp_path / "plan" / "SKILL.md"
    skill_file.parent.mkdir()
    skill_file.write_text(fake_content)

    import src.channels.telegram as tg
    original = tg._SKILLS_DIR
    tg._SKILLS_DIR = tmp_path
    try:
        result = tg._skill("plan")
    finally:
        tg._SKILLS_DIR = original

    assert result == fake_content


def test_skill_appends_args_not_format(tmp_path):
    """User args are appended as suffix — str.format() is never called."""
    # Skill content with JSON braces that would crash str.format()
    fake_content = '# Note skill\n\nRun: gws tasks insert --params \'{"tasklist":"@default"}\''
    skill_file = tmp_path / "note" / "SKILL.md"
    skill_file.parent.mkdir()
    skill_file.write_text(fake_content)

    import src.channels.telegram as tg
    original = tg._SKILLS_DIR
    tg._SKILLS_DIR = tmp_path
    try:
        result = tg._skill("note", args="buy milk")
    finally:
        tg._SKILLS_DIR = original

    assert "User input: buy milk" in result
    assert fake_content in result  # original content preserved


def test_skill_no_args_returns_content_unchanged(tmp_path):
    fake_content = "# Week skill"
    skill_file = tmp_path / "week" / "SKILL.md"
    skill_file.parent.mkdir()
    skill_file.write_text(fake_content)

    import src.channels.telegram as tg
    original = tg._SKILLS_DIR
    tg._SKILLS_DIR = tmp_path
    try:
        result = tg._skill("week")
    finally:
        tg._SKILLS_DIR = original

    assert result == fake_content
