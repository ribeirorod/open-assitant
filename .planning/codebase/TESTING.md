# Testing Patterns

**Analysis Date:** 2026-03-25

## Framework

- **Runner:** pytest `>=8.0` — Config: `pyproject.toml` `[tool.pytest.ini_options]`
- **Async support:** pytest-asyncio `>=0.24` — mode: `asyncio_mode = "auto"` (all async tests run automatically, no `@pytest.mark.asyncio` required by default, though some tests add it explicitly for clarity)
- **Assertions:** stdlib `assert` statements — no third-party assertion library
- **Mocking:** `unittest.mock` — `patch`, `AsyncMock`, `MagicMock`, `mock_open`
- **Commands:**
  - Run all: `pytest`
  - Run single file: `pytest tests/test_scheduler.py`
  - With verbose output: `pytest -v`
  - Coverage: not configured; no coverage command exists

## Organization

- **Location:** All tests in `tests/` directory at project root (separate from source)
- **Naming:** Files follow `test_<module_or_feature>.py` — one test file per feature area
- **Test functions:** `test_<what_it_does>` in snake_case — descriptive, not `test_1`
- **No test classes** — all tests are standalone functions

## Test Files and What They Cover

| File | What is tested |
|------|---------------|
| `tests/test_core_prompt.py` | `SYSTEM_PROMPT` in `src/agent/core.py` — guardrails, no hardcoded `gws` commands |
| `tests/test_scheduler.py` | `src/scheduler/scheduler.py` — job registration, coroutine type, notification gating |
| `tests/test_schedules.py` | The live `~/.open-assistant/schedules.yaml` file — schema validity, required fields, expected job names |
| `tests/test_skill_loader.py` | `_skill()` in `src/channels/telegram.py` — file loading, arg appending, no `str.format()` injection |
| `tests/test_missed_message.py` | `_is_missed_message()` and `_record_reply()` in `src/channels/telegram.py` |
| `tests/test_memory.py` | Live `~/.open-assistant/memory/` files — existence, index format, procrastination entry format |
| `tests/test_memory_sync.py` | `src/memory/sync.py` — pull, push, sync, metadata persistence, GDrive availability check |
| `tests/test_telegram_commands.py` | `build_telegram_app()` — all Telegram commands are registered |

## Patterns

### Sync test (simple assertion)
```python
def test_system_prompt_has_no_tool_documentation():
    from src.agent.core import SYSTEM_PROMPT
    assert "gws" not in SYSTEM_PROMPT
```

### Async test with AsyncMock and patch
```python
@pytest.mark.asyncio
async def test_run_task_sends_notification_on_non_empty_response():
    task = {"name": "morning-briefing", "prompt": "...", "notify": {"telegram": ["123456789"]}}
    from src.scheduler import scheduler as sched_mod
    with patch("src.scheduler.scheduler.ask_agent", new=AsyncMock(return_value="1. Check email")), \
         patch("src.channels.telegram_notify.send_telegram_message", new=AsyncMock()) as mock_send:
        await sched_mod._run_task(task)
        mock_send.assert_awaited_once_with("123456789", "1. Check email")
```

### Filesystem isolation with tmp_path and monkeypatch
```python
@pytest.mark.asyncio
async def test_pull_downloads_new_file(tmp_path, monkeypatch):
    monkeypatch.setattr("src.memory.sync.MEMORY_DIR", tmp_path)
    monkeypatch.setattr("src.memory.sync.SYNC_META", tmp_path / ".sync-meta.json")
    # ... test using tmp_path instead of real ~/.open-assistant/
```

### Integration test against live files (requires deployed environment)
```python
# tests/test_schedules.py and tests/test_memory.py
# These read from ~/.open-assistant/ — they pass only in a configured environment.
SCHEDULES_PATH = pathlib.Path.home() / ".open-assistant" / "schedules.yaml"

def test_schedules_file_exists():
    assert SCHEDULES_PATH.exists(), f"schedules.yaml not found at {SCHEDULES_PATH}"
```

### Command handler registration test
```python
@pytest.fixture
def tg_app():
    with patch.dict(os.environ, {"OA_TELEGRAM_BOT_TOKEN": "1234567890:FAKE_TOKEN_FOR_TESTING"}):
        import importlib
        import src.config as cfg
        importlib.reload(cfg)
        cfg.settings.telegram_bot_token = "1234567890:FAKE_TOKEN_FOR_TESTING"
        from src.channels.telegram import build_telegram_app
        return build_telegram_app()

def test_inbox_command_registered(tg_app):
    cmds = _registered_commands(tg_app)
    assert "inbox" in cmds
```

### Mock helper objects
```python
def _make_update(age_seconds: float) -> MagicMock:
    msg_date = datetime.now(timezone.utc) - timedelta(seconds=age_seconds)
    message = MagicMock()
    message.date = msg_date
    update = MagicMock()
    update.message = message
    return update
```

## Mocking

- **Framework:** `unittest.mock` — `patch` for module-level attributes, `AsyncMock` for coroutines, `MagicMock` for object mocks
- **What to mock:**
  - `ask_agent` — always mocked in scheduler tests; never call the real Claude SDK in unit tests
  - `send_telegram_message` / `send_notification` — always mocked to prevent real network calls
  - `src.memory.sync._run_gws` — mocked in memory sync tests; the `gws` binary is not available in CI
  - `src.memory.sync._get_memory_folder_id`, `_list_remote_files`, `_download_file`, `_upload_file` — mocked to test sync logic without GDrive
  - `MEMORY_DIR` and `SYNC_META` — redirected to `tmp_path` via `monkeypatch.setattr`
- **What NOT to mock:**
  - Pure synchronous logic (e.g. `_is_missed_message`, `_safe_filename`, `_load_sync_meta`) — test against real objects
  - Filesystem operations when using `tmp_path` — let them run against the temp directory
- **Patch target is always the import site** (where the name is used), not the definition site:
  - Correct: `patch("src.scheduler.scheduler.ask_agent", ...)`
  - Incorrect: `patch("src.agent.core.ask_agent", ...)`

## Fixtures and Test Data

- **`tmp_path`** (built-in pytest fixture) — used for any test that reads/writes files
- **`monkeypatch`** (built-in pytest fixture) — used to redirect module-level path constants (`MEMORY_DIR`, `SCHEDULES_PATH`, `SYNC_META`) to temp locations
- **`tg_app`** fixture in `tests/test_telegram_commands.py` — builds a Telegram Application with a fake bot token via `patch.dict(os.environ, ...)`
- No shared fixtures file (`conftest.py`) exists — fixtures are defined inline in each test file

## Coverage

- **Target:** None enforced — no coverage configuration in `pyproject.toml`
- **Coverage command:** Not configured
- **Known coverage gaps:**
  - `src/agent/core.py` — `ask_agent`, `_get_or_create_client`, `reset_agent`, `shutdown_all` are not unit-tested (would require a live Claude SDK connection); only `SYSTEM_PROMPT` content is verified
  - `src/channels/telegram.py` — `_handle_message`, `_handle_voice`, `_transcribe*`, `_synthesize`, `_dispatch`, `_send_markdown` have no tests; the module is tested only for command registration and private helper functions
  - `src/channels/whatsapp.py` — no tests at all
  - `src/channels/telegram_notify.py` — no tests at all (only mocked as a dependency)
  - `src/main.py` — no tests for the startup/shutdown sequence
  - `src/agent/session_store.py` — no direct tests; tested implicitly via `test_missed_message.py`
  - STT/TTS fallback chain (`_transcribe` trying Groq → OpenAI → Deepgram) — not tested

## Test Types

- **Unit:** The majority. Test individual functions with all external dependencies mocked.
- **Integration (live environment):** `tests/test_schedules.py` and `tests/test_memory.py` read from real `~/.open-assistant/` files. These tests pass only when the assistant is fully deployed and configured. They verify deployment state, not code logic.
- **E2E:** Not present. No end-to-end tests exercise the full Telegram → agent → response pipeline.

## How to Run

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run all tests
pytest

# Run only unit tests (skip live-env tests that need ~/.open-assistant/)
pytest tests/test_core_prompt.py tests/test_scheduler.py tests/test_skill_loader.py \
       tests/test_missed_message.py tests/test_memory_sync.py tests/test_telegram_commands.py

# Run a single test by name
pytest tests/test_scheduler.py::test_run_task_skips_notification_on_empty_response -v
```

Note: `tests/test_schedules.py` and `tests/test_memory.py` require a deployed environment with `~/.open-assistant/schedules.yaml` and `~/.open-assistant/memory/` populated. They will fail in a bare development environment.
