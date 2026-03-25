# Coding Conventions

**Analysis Date:** 2026-03-25

## Naming

- **Files:** `snake_case.py` — Example: `session_store.py`, `telegram_notify.py`
- **Modules/packages:** `snake_case` — Example: `src/channels/`, `src/memory/`
- **Functions:** `snake_case` — Example: `ask_agent`, `start_scheduler`
- **Private functions:** Leading underscore — Example: `_run_task`, `_get_or_create_client`, `_dispatch`
- **Variables/constants:** `UPPER_SNAKE_CASE` for module-level constants — Example: `SCHEDULES_PATH`, `MISSED_MESSAGE_THRESHOLD`, `MAX_TG_MESSAGE_LENGTH`
- **Classes:** `PascalCase` — Example: `Settings`
- **Type annotations:** Always present on function signatures; use `from __future__ import annotations` for forward references

## Style & Linting

- **Formatter/Linter:** Ruff — Config: `pyproject.toml` `[tool.ruff]`
  - `line-length = 100`
  - `target-version = "py310"`
- **`from __future__ import annotations`** is always the first import in every source file.
- No `TODO`, `FIXME`, or `HACK` markers exist in the codebase.
- Docstrings are present on all public functions and modules; they describe behaviour and context, not just names.

## Import Organization

1. `from __future__ import annotations` (always first)
2. Standard library (`asyncio`, `json`, `logging`, `pathlib`, etc.)
3. Third-party packages (`pydantic`, `apscheduler`, `yaml`, `telegram`, etc.)
4. Internal project imports (`from src.config import settings`, `from src.agent.core import ask_agent`)

Private/deferred imports (to avoid circular dependencies at module load time) are placed inline inside function bodies and annotated with a comment:

```python
from src.channels.telegram_notify import send_telegram_message  # deferred to avoid circular import
```

- **No path aliases** — all internal imports use the full `src.*` package path.

## Config / Settings Pattern

All configuration lives in a single `Settings` class in `src/config.py`, backed by `pydantic-settings`.

```python
class Settings(BaseSettings):
    model_config = {"env_prefix": "OA_", "env_file": ".env", "extra": "ignore"}

    telegram_bot_token: str = ""
    webhook_port: int = 8080
```

Rules:
- `OA_` prefix for all app-specific settings (e.g. `OA_TELEGRAM_BOT_TOKEN`).
- Third-party keys that have established env var names (e.g. `PERPLEXITY_API_KEY`) use `validation_alias` to read without prefix.
- A module-level singleton `settings = Settings()` is imported wherever config is needed.
- Never read `os.environ` directly outside of `src/config.py`.

## Async Patterns

- All I/O-bound operations (agent queries, HTTP calls, GDrive CLI, Telegram bot) are `async def`.
- The event loop is started exactly once at the top level: `asyncio.run(_run())` in `src/main.py`.
- Background tasks use `asyncio.create_task(...)` with explicit `asyncio.Event()` stop signals:

```python
stop = asyncio.Event()
typing_task = asyncio.create_task(_keep_typing(update, stop))
try:
    response = await ask_agent(...)
finally:
    stop.set()
    typing_task.cancel()
    try:
        await typing_task
    except asyncio.CancelledError:
        pass
```

- `asyncio.gather(*tasks)` is used in `src/main.py` to run concurrent services (uvicorn + Telegram polling).
- Subprocess calls use `asyncio.create_subprocess_exec` with `asyncio.wait_for` timeout guards (see `src/memory/sync.py`).
- Scheduled tasks use `AsyncIOScheduler` from APScheduler; all job functions must be `async def` (verified by test).

## Logging Conventions

- Every module creates its own logger at the top: `log = logging.getLogger(__name__)`
- Root logging is configured once in `src/main.py`:
  ```python
  logging.basicConfig(
      level=logging.INFO,
      format="%(asctime)s %(levelname)-8s %(name)s  %(message)s",
  )
  ```
- Log levels follow this pattern:
  - `log.info(...)` — normal operational events (request received, task started, session resumed)
  - `log.warning(...)` — recoverable failures (STT provider failed, GDrive unavailable, session resume failed)
  - `log.error(...)` — unrecoverable failures (upload failed, folder creation failed)
  - `log.debug(...)` — low-level diagnostic detail (gws command strings, disconnect errors)
  - `log.exception(...)` — unexpected exceptions that bubble up (handler errors, transcription failure)
- Log messages use `%s` lazy formatting, never f-strings: `log.info("task %s done", name)`
- Sensitive data (tokens, keys) is never logged.

## Error Handling Patterns

- Exceptions from external services are caught at the call site and converted to log warnings/errors. The caller continues or returns a sentinel:

```python
try:
    result = await provider(audio_bytes, filename)
except Exception as exc:
    log.warning("STT provider %s failed: %s", provider.__name__, exc)
```

- JSON parsing and filesystem I/O are always wrapped to return safe defaults:

```python
try:
    return json.loads(p.read_text())
except (json.JSONDecodeError, OSError):
    return None
```

- `contextlib.suppress(Exception)` is used for teardown code where failures are expected and inconsequential (graceful shutdown).
- The agent's `ask_agent()` returns `"(no response)"` as a sentinel string on empty results — callers check for this explicitly.

## Skill File Format (SKILL.md)

Skills live in `.claude/skills/<name>/SKILL.md`. Two formats exist:

**With YAML front matter** (newer skills — used by the `Skill` tool for auto-discovery):
```markdown
---
name: note
description: Use when the user sends /note...
---

# Skill Title

## Steps

1. ...
```

**Without front matter** (older skills — loaded directly by `_skill()` in `src/channels/telegram.py`):
```markdown
# Skill Title

CONSTRAINTS:
- ...

## Step 1: ...
```

Rules for skills:
- Skills are pure documentation for the Claude agent — they contain no Python.
- Skills use imperative headings: `## Step 1:`, `## Steps`, `## Output format`.
- Skills never embed hardcoded user data (IDs, names). User-specific data comes from memory files.
- Skills contain exact `gws` CLI commands in fenced bash blocks.
- `SYSTEM_PROMPT` in `src/agent/core.py` must NOT reference specific `gws` commands — those belong exclusively in skill files (enforced by `test_core_prompt.py`).
- User arguments are appended to skill content with `\n\nUser input: {args}` — never injected via `str.format()` (would crash on JSON braces in skill content).

## Scheduled Task Definition (YAML + Scheduler Pattern)

Scheduled tasks are defined in `~/.open-assistant/schedules.yaml`, not in Python. The scheduler (`src/scheduler/scheduler.py`) reads this file at startup and registers one APScheduler job per task.

Required fields per task:
```yaml
tasks:
  - name: morning-briefing          # unique job id (kebab-case)
    cron: "0 8 * * 0-4"             # APScheduler crontab (0=Monday, not 0=Sunday)
    prompt: >
      Give me a morning briefing.   # plain-text prompt sent to ask_agent()
    notify:
      telegram: ["123456789"]       # Telegram chat IDs (strings)
      whatsapp: ["15551234567"]     # WhatsApp phone numbers (optional)
```

Rules:
- `cron` must be a string, even if it looks numeric.
- APScheduler's `CronTrigger.from_crontab()` uses `0=Monday` (Python weekday), not `0=Sunday` (Unix cron). Use `0-4` for Monday–Friday.
- Scheduled jobs use `chat_id=f"sched:{name}"` — distinct from interactive chat IDs so sessions don't cross-contaminate.
- Silent tasks (where the agent returns empty or `"(no response)"`) must not trigger notifications — the scheduler enforces this.
- Never add dedicated Python modules or multi-entry workarounds for scheduling; all new scheduled tasks go in the YAML file.

## Module Design

- **Barrel files:** `src/__init__.py`, `src/agent/__init__.py`, etc. are empty (no re-exports). Import from the specific module directly.
- **Single responsibility per module:** Each file owns one concern — `config.py` for settings, `session_store.py` for persistence, `scheduler.py` for cron, `sync.py` for GDrive I/O.
- **Public API functions** are named without leading underscore and have docstrings. Private helpers have `_` prefix and minimal or no docstring.
- **No circular imports:** Channel adapters (`telegram.py`, `whatsapp.py`) import from `src.agent.core`; `core.py` never imports from channels. Deferred imports are used in `scheduler.py` to break circular dependency on channel modules.
