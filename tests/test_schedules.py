# tests/test_schedules.py
import pathlib
import pytest
import yaml


SCHEDULES_PATH = pathlib.Path.home() / ".open-assistant" / "schedules.yaml"
EXPECTED_JOB_NAMES = {
    "morning-briefing",
    "evening-review",
    "weekly-planning",
    "midweek-pulse",
    "bureaucracy-check",
    "pulse",
    "inbox-manager",
}


def test_schedules_file_exists():
    assert SCHEDULES_PATH.exists(), f"schedules.yaml not found at {SCHEDULES_PATH}"


def test_schedules_valid_yaml():
    data = yaml.safe_load(SCHEDULES_PATH.read_text())
    assert isinstance(data, dict)
    assert "tasks" in data
    assert isinstance(data["tasks"], list)


def test_all_jobs_present():
    data = yaml.safe_load(SCHEDULES_PATH.read_text())
    names = {t["name"] for t in data["tasks"]}
    for expected in EXPECTED_JOB_NAMES:
        assert expected in names, f"Missing scheduled job: {expected}"


def test_each_job_has_required_fields():
    data = yaml.safe_load(SCHEDULES_PATH.read_text())
    for task in data["tasks"]:
        assert "name" in task, f"Job missing 'name': {task}"
        assert "cron" in task, f"Job '{task.get('name')}' missing 'cron'"
        assert "prompt" in task, f"Job '{task.get('name')}' missing 'prompt'"
        assert "notify" in task, f"Job '{task.get('name')}' missing 'notify'"
        assert "telegram" in task["notify"], f"Job '{task.get('name')}' missing notify.telegram"
        assert len(task["notify"]["telegram"]) > 0


def test_cron_expressions_are_strings():
    data = yaml.safe_load(SCHEDULES_PATH.read_text())
    for task in data["tasks"]:
        assert isinstance(task["cron"], str), f"cron must be a string in job '{task.get('name')}'"
