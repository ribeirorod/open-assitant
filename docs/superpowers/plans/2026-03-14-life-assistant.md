# Life Assistant Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a personal memory system, five Telegram commands, and five scheduled jobs so the assistant knows João's life context and proactively helps him manage it.

**Architecture:** A flat markdown memory store at `~/.open-assistant/memory/` (read/written by the agent via the `Read`/`Write` tools) is injected via the system prompt so every session and scheduled job is personalised. Five new Telegram command handlers delegate structured prompts to the agent. Five cron jobs push proactive briefings to Telegram.

**Tech Stack:** python-telegram-bot 21+, APScheduler 3, Claude Agent SDK, `gws` CLI, PyYAML, pytest + pytest-asyncio

**Spec:** `docs/superpowers/specs/2026-03-13-life-assistant-design.md`

---

## Chunk 1: Memory System & System Prompt

### Task 1: Create memory directory and skeleton files

**Files:**
- Create: `~/.open-assistant/memory/index.md`
- Create: `~/.open-assistant/memory/projects.md`
- Create: `~/.open-assistant/memory/commitments.md`
- Create: `~/.open-assistant/memory/preferences.md`
- Create: `~/.open-assistant/memory/procrastination.md`
- Create: `~/.open-assistant/memory/german-life.md`
- Create: `tests/test_memory.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_memory.py
import pathlib
import pytest


MEMORY_DIR = pathlib.Path.home() / ".open-assistant" / "memory"
EXPECTED_FILES = [
    "index.md",
    "projects.md",
    "commitments.md",
    "preferences.md",
    "procrastination.md",
    "german-life.md",
]


def test_memory_dir_exists():
    assert MEMORY_DIR.is_dir(), f"Memory directory not found: {MEMORY_DIR}"


def test_all_memory_files_exist():
    for name in EXPECTED_FILES:
        assert (MEMORY_DIR / name).exists(), f"Missing memory file: {name}"


def test_index_format():
    """Every non-blank line in index.md must be '- topic: description → filename'."""
    index = (MEMORY_DIR / "index.md").read_text()
    for line in index.strip().splitlines():
        if not line.strip():
            continue
        assert line.startswith("- "), f"Bad index line: {line!r}"
        assert " → " in line, f"Missing ' → ' in index line: {line!r}"


def test_procrastination_entry_format():
    """Entries must start with '- [YYYY-MM-DD added]' so age can be calculated."""
    content = (MEMORY_DIR / "procrastination.md").read_text()
    import re
    entries = [l for l in content.splitlines() if l.startswith("- [")]
    for entry in entries:
        assert re.match(r"^- \[\d{4}-\d{2}-\d{2} added\]", entry), (
            f"Bad procrastination entry format: {entry!r}"
        )
```

- [ ] **Step 2: Run test to confirm it fails**

```bash
cd /Users/beam/open-assitant && uv run pytest tests/test_memory.py -v
```

Expected: FAIL — `Memory directory not found`

- [ ] **Step 3: Create the memory directory and files**

```bash
mkdir -p ~/.open-assistant/memory
```

Create `~/.open-assistant/memory/index.md`:

```markdown
- projects: current projects, status and next actions → projects.md
- commitments: key life commitments and deadlines → commitments.md
- preferences: personal style, focus hours, habits → preferences.md
- procrastination: known avoidance patterns and items being avoided → procrastination.md
- german-life: bureaucracy, tax and registration deadlines → german-life.md
```

Create `~/.open-assistant/memory/projects.md`:

```markdown
# Projects

> This file is maintained by Open Assistant. Update via /update or in conversation.

## Active Projects

<!-- Agent will populate during bootstrap session -->
```

Create `~/.open-assistant/memory/commitments.md`:

```markdown
# Commitments

> Key life commitments, deadlines, and recurring obligations.

## Immediate
<!-- Agent will populate during bootstrap session -->

## Recurring
<!-- German bureaucracy, anniversaries, health appointments, etc. -->
```

Create `~/.open-assistant/memory/preferences.md`:

```markdown
# Preferences

> Personal work style, habits, and communication preferences.

## Work Style
<!-- e.g. focus hours, deep work blocks, preferred tools -->

## Health & Fitness
<!-- gym schedule, targets -->

## Communication
<!-- tone, response style, languages -->

## Other Habits
<!-- piano practice, family time, etc. -->
```

Create `~/.open-assistant/memory/procrastination.md`:

```markdown
# Procrastination Tracker

> Format: - [YYYY-MM-DD added] Item description
> Agent surfaces items older than 3 days in every morning briefing.

<!-- Agent will add items when it detects avoidance patterns -->
```

Create `~/.open-assistant/memory/german-life.md`:

```markdown
# German Life — Bureaucracy & Deadlines

> Deadlines, renewals, and registrations for living in Germany.

## Annual
<!-- Steuererklärung deadline, health insurance renewal, etc. -->

## Post-Baby (fill in once baby arrives)
<!-- Geburtsurkunde: within 7 days of birth -->
<!-- Krankenkasse registration: immediate -->
<!-- Kindergeld application: within 6 months -->
<!-- Elternzeit notification: 7 weeks before start -->

## One-off / Pending
<!-- Ad-hoc bureaucracy tasks -->
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
uv run pytest tests/test_memory.py -v
```

Expected: PASS — all 4 tests green (`test_memory_dir_exists`, `test_all_memory_files_exist`, `test_index_format`, `test_procrastination_entry_format` — the last one passes because there are no entries yet, so no assertions run)

- [ ] **Step 5: Commit**

```bash
git add tests/test_memory.py
git commit -m "test: add memory system structure tests"
```

> Note: `~/.open-assistant/memory/` lives outside the repo and is never committed. The test suite verifies its existence at runtime.

---

### Task 2: Update system prompt in `src/agent/core.py`

**Files:**
- Modify: `src/agent/core.py` — extend `SYSTEM_PROMPT`
- Test: `tests/test_core_prompt.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_core_prompt.py


def test_system_prompt_has_memory_instructions():
    from src.agent.core import SYSTEM_PROMPT
    assert "~/.open-assistant/memory/" in SYSTEM_PROMPT
    assert "index.md" in SYSTEM_PROMPT
    assert "Read tool" in SYSTEM_PROMPT
    assert "Write tool" in SYSTEM_PROMPT


def test_system_prompt_limits_daily_tasks():
    from src.agent.core import SYSTEM_PROMPT
    assert "3 meaningful priorities" in SYSTEM_PROMPT


def test_system_prompt_has_procrastination_protocol():
    from src.agent.core import SYSTEM_PROMPT
    assert "procrastinat" in SYSTEM_PROMPT.lower()


def test_system_prompt_scheduled_jobs_must_not_write():
    """Scheduled job prompts must include the DO NOT write instruction."""
    from src.agent.core import SYSTEM_PROMPT
    assert "DO NOT write to memory" in SYSTEM_PROMPT or "Scheduled job prompts will say" in SYSTEM_PROMPT
```

- [ ] **Step 2: Ensure `src` is importable in tests**

Add `pythonpath = ["."]` to `[tool.pytest.ini_options]` in `pyproject.toml`:

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
pythonpath = ["."]
```

- [ ] **Step 3: Run tests to confirm they fail**

```bash
uv run pytest tests/test_core_prompt.py -v
```

Expected: FAIL — `assert "~/.open-assistant/memory/" in SYSTEM_PROMPT`

- [ ] **Step 4: Extend `SYSTEM_PROMPT` in `src/agent/core.py`**

Open `src/agent/core.py`. The current `SYSTEM_PROMPT` ends around line 54. Replace the entire `SYSTEM_PROMPT` constant with:

```python
SYSTEM_PROMPT = """\
You are Open Assistant — a personal Google Workspace helper and life organiser running on Telegram.

You have access to the `gws` CLI via the Bash tool for Gmail, Calendar, Drive, Sheets, Docs, and Tasks.

Quick reference:
  gws gmail +send --to <email> --subject <subj> --body <body>
  gws gmail +triage
  gws calendar +agenda
  gws calendar events insert --params '{"calendarId":"primary","requestBody":{"summary":"...","start":{"dateTime":"..."},"end":{"dateTime":"..."}}}'
  gws calendar events list --params '{"calendarId":"primary","timeMin":"<RFC3339>","timeMax":"<RFC3339>","singleEvents":true,"orderBy":"startTime"}'
  gws drive files list --params '{"pageSize":10}'
  gws tasks tasks list --params '{"tasklist":"<id>"}'
  gws tasks tasks list --params '{"tasklist":"@default"}'

MEMORY — your persistent knowledge base lives at ~/.open-assistant/memory/:
- At the start of every response, read index.md with the Read tool.
- Then read whichever topic files are relevant to the current request (see index.md for the list).
- When you learn something new (project update, deadline, preference, avoidance pattern), update the
  relevant memory file immediately with the Write tool. Overwrite the whole file — Read it first,
  then Write the updated version.
- If a topic has no existing file, create one and add a one-line entry to index.md.
- Procrastination entries must use this format: "- [YYYY-MM-DD added] Item description"
  so age in days can be calculated.
- Scheduled job prompts will say "DO NOT write to memory" — obey that instruction.

PLANNING DISCIPLINE:
- When planning a day or week, propose at most 3 meaningful priorities. If the user lists more,
  flag it: "That's more than 3 — which would you drop?"
- Protect time for gym (min 3 sessions/week), family, and piano practice when scheduling.

PROCRASTINATION PROTOCOL:
- Surface items from procrastination.md that are older than 3 days in every /plan and morning briefing.
- If an item keeps appearing across multiple sessions without progress, name it directly:
  "You've been avoiding [X] for N days. What's actually blocking you?"

CONFIRMATION BEFORE ACTION:
- Always confirm before sending emails, creating calendar events, or modifying/deleting tasks.
  One short sentence is enough: "Ready to send — confirm?"
- Never auto-create or auto-send anything.

FORMATTING — responses are rendered as Markdown in Telegram:
- Use **bold** for labels and headings, not decorative emphasis.
- Use bullet lists or numbered lists for structured data.
- Use `inline code` for values like dates, IDs, file names.
- Use --- to visually separate distinct sections.
- Never use emoji or emoticons.
- Never start with a greeting or sign off at the end.
- No filler phrases ("Sure!", "Of course!", "Great question!", "Let me help you with that").

BREVITY:
- Default to 3–6 lines. Only go longer if the data genuinely requires it.
- For lists, show max 5 items then summarise ("…and 3 more").
"""
```

- [ ] **Step 5: Run tests to confirm they pass**

```bash
uv run pytest tests/test_core_prompt.py -v
```

Expected: PASS — all 4 tests green

- [ ] **Step 6: Smoke-test the running bot**

Start the bot (`uv run open-assistant`) and send any message via Telegram. Check logs show the agent reading `index.md` before responding. If it doesn't, verify the system prompt was saved correctly.

- [ ] **Step 7: Commit**

```bash
git add pyproject.toml src/agent/core.py tests/test_core_prompt.py
git commit -m "feat: add memory system instructions and planning discipline to system prompt"
```

---

## Chunk 2: Telegram Command Handlers

### Task 3: Add `_dispatch` helper and `/chatid` utility command

**Files:**
- Modify: `src/channels/telegram.py`
- Create: `tests/test_telegram_commands.py`

The existing `_handle_message` and `_handle_voice` duplicate the typing-indicator pattern. Extract it into `_dispatch`, then use it for all new command handlers.

- [ ] **Step 1: Write the failing test for command registration**

```python
# tests/test_telegram_commands.py
import os
import pytest
from unittest.mock import patch


@pytest.fixture
def tg_app():
    """Build the Telegram app with a fake token."""
    with patch.dict(os.environ, {"OA_TELEGRAM_BOT_TOKEN": "1234567890:FAKE_TOKEN_FOR_TESTING"}):
        # Re-import settings so the env var takes effect
        import importlib
        import src.config as cfg
        importlib.reload(cfg)
        cfg.settings.telegram_bot_token = "1234567890:FAKE_TOKEN_FOR_TESTING"

        from src.channels.telegram import build_telegram_app
        from telegram.ext import CommandHandler
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
        assert cmd in cmds, f"/{ cmd } not registered"
```

- [ ] **Step 2: Run test to confirm it fails**

```bash
uv run pytest tests/test_telegram_commands.py -v
```

Expected: FAIL — `plan not registered`

- [ ] **Step 3: Add `_dispatch` helper to `src/channels/telegram.py`**

Open `src/channels/telegram.py`. After the `_keep_typing` function (around line 73), add:

```python
async def _dispatch(update: Update, prompt: str) -> None:
    """Route any prompt through the agent with typing indicator."""
    if not _is_allowed(update):
        return
    chat_id = str(update.effective_chat.id)
    stop = asyncio.Event()
    typing_task = asyncio.create_task(_keep_typing(update, stop))
    try:
        response = await ask_agent(prompt, chat_id)
    finally:
        stop.set()
        typing_task.cancel()
    await _send_markdown(update, response)
```

- [ ] **Step 4: Add `/chatid` command handler**

After `_dispatch`, add:

```python
async def _chatid(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Return the user's Telegram chat ID — needed to configure schedules.yaml."""
    if not _is_allowed(update):
        return
    await update.message.reply_text(f"Your chat ID: `{update.effective_chat.id}`", parse_mode="MarkdownV2")
```

- [ ] **Step 5: Register `/chatid` in `build_telegram_app`**

In `build_telegram_app()`, after `app.add_handler(CommandHandler("reset", _reset))`, add:

```python
app.add_handler(CommandHandler("chatid", _chatid))
```

- [ ] **Step 6: Run test to confirm `/chatid` is registered (partial pass)**

```bash
uv run pytest tests/test_telegram_commands.py::test_original_commands_still_registered tests/test_telegram_commands.py::test_new_commands_registered -v
```

Expected: FAIL — `plan not registered` (chatid now passes, others still missing)

- [ ] **Step 7: Commit partial progress**

```bash
git add src/channels/telegram.py tests/test_telegram_commands.py
git commit -m "feat: add _dispatch helper and /chatid command"
```

---

### Task 4: Add `/plan`, `/week`, `/note`, `/avoid`, `/update` command handlers

**Files:**
- Modify: `src/channels/telegram.py`

- [ ] **Step 1: Add all five command handlers after `_chatid`**

```python
# ── Life-assistant commands ──────────────────────────────────────────────────

_PLAN_PROMPT = """\
/plan — run the daily planning workflow:
1. Read ~/.open-assistant/memory/index.md then projects.md, commitments.md, preferences.md, procrastination.md.
2. Run: gws calendar +agenda
3. Run: gws gmail +triage
4. Run: gws tasks tasks list --params '{"tasklist":"@default"}'
5. Produce a structured daily plan:
   **Today's 3 priorities** (realistic given the calendar — no more than 3, bold them)
   **Emails needing action** (max 3, one line each with suggested next step)
   **One item to face today** (oldest item in procrastination.md by added date, if any >3 days old)
6. Ask: "Does this look right?"
Max 15 lines. Do NOT write to memory during this scheduled prompt."""


_WEEK_PROMPT = """\
/week — run the weekly overview workflow:
1. Read all files in ~/.open-assistant/memory/.
2. Use Bash to compute next Monday and Sunday in Europe/Berlin time:
   python3 -c "from datetime import datetime, timedelta; import zoneinfo; tz=zoneinfo.ZoneInfo('Europe/Berlin'); now=datetime.now(tz); offset=now.strftime('%z'); offset=offset[:3]+':'+offset[3:]; today=now.date(); monday=today+timedelta(days=(7-today.weekday())%7 or 7); sunday=monday+timedelta(days=6); print(monday.isoformat()+'T00:00:00'+offset, sunday.isoformat()+'T23:59:59'+offset)"
3. Run: gws calendar events list --params '{"calendarId":"primary","timeMin":"<MONDAY>","timeMax":"<SUNDAY>","singleEvents":true,"orderBy":"startTime"}'
4. Run: gws tasks tasks list --params '{"tasklist":"@default"}'
5. Output:
   - Days that look overloaded (>3 commitments)
   - Missing time blocks for: gym (need 3 sessions), family/relationship, piano
   - Suggested time blocks (list only — do NOT create calendar events)
   - One thing to defer if the week is too full
6. Ask: "Want me to create these blocks?" — only create after explicit confirmation."""


_AVOID_PROMPT = """\
/avoid — surface procrastinated items:
1. Read ~/.open-assistant/memory/procrastination.md.
2. Run: gws tasks tasks list --params '{"tasklist":"@default"}' to find tasks with old due dates.
3. List avoided items by name with days elapsed (calculate from [YYYY-MM-DD added] in procrastination.md).
4. Ask: "Which one can you do 30 minutes on today?"
5. When user picks one:
   a. Compute current time in Berlin: python3 -c "from datetime import datetime; import zoneinfo; tz=zoneinfo.ZoneInfo('Europe/Berlin'); now=datetime.now(tz); print(now.strftime('%H:%M'), now.isoformat())"
   b. Run: gws calendar events list --params '{"calendarId":"primary","timeMin":"<NOW_ISO>","timeMax":"<END_OF_DAY_ISO>","singleEvents":true,"orderBy":"startTime"}' to find free slots.
   c. Identify first gap of ≥30 minutes. If none found or parsing unclear, ask: "What time works for you?"
   d. Propose: "I can block HH:MM–HH:MM for [item]. Confirm?"
   e. Only create the calendar event after explicit confirmation. Event title: "Focus: [item name]" """


_UPDATE_PROMPT_TEMPLATE = """\
/update {args}— update memory:
1. Read ~/.open-assistant/memory/index.md.
2. Read the memory file most relevant to the topic "{args}".
3. Ask what's changed (if the user hasn't already explained in this message).
4. Write the updated content back to the file using the Write tool.
5. Confirm: "Updated [filename] — here's what changed: ..."."""


async def _plan(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await _dispatch(update, _PLAN_PROMPT)


async def _week(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await _dispatch(update, _WEEK_PROMPT)


async def _note(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    args = " ".join(ctx.args) if ctx.args else ""
    if not args:
        await update.message.reply_text("Usage: /note [your note text]")
        return
    prompt = (
        f"/note — capture this: {args}\n\n"
        "Determine whether this belongs in Google Tasks, a memory file, or both.\n"
        "- If it is a task or reminder: add it to Google Tasks under the right project label.\n"
        "- If it is a goal, preference, or personal fact: write it to the appropriate memory file.\n"
        "- If both apply: do both.\n"
        "Confirm exactly what you stored and where."
    )
    await _dispatch(update, prompt)


async def _avoid(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await _dispatch(update, _AVOID_PROMPT)


async def _update(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    args = " ".join(ctx.args) if ctx.args else ""
    await _dispatch(update, _UPDATE_PROMPT_TEMPLATE.format(args=f"'{args}' " if args else ""))
```

- [ ] **Step 2: Register all five commands in `build_telegram_app()`**

In `build_telegram_app()`, after `app.add_handler(CommandHandler("chatid", _chatid))`, add:

```python
app.add_handler(CommandHandler("plan", _plan))
app.add_handler(CommandHandler("week", _week))
app.add_handler(CommandHandler("note", _note))
app.add_handler(CommandHandler("avoid", _avoid))
app.add_handler(CommandHandler("update", _update))
```

- [ ] **Step 3: Run all command tests**

```bash
uv run pytest tests/test_telegram_commands.py -v
```

Expected: PASS — all tests green

- [ ] **Step 4: Run full test suite to check for regressions**

```bash
uv run pytest -v
```

Expected: PASS — all tests green (or only pre-existing failures)

- [ ] **Step 5: Manual smoke test**

Start the bot and send `/chatid` — confirm it replies with your numeric chat ID.
Send `/plan` — confirm the agent reads memory files and calls `gws` tools before responding.

- [ ] **Step 6: Commit**

```bash
git add src/channels/telegram.py
git commit -m "feat: add /plan /week /note /avoid /update /chatid Telegram commands"
```

---

## Chunk 3: Scheduled Jobs & Bootstrap

### Task 5: Fix pre-existing scheduler bug in `src/scheduler/scheduler.py`

**Files:**
- Modify: `src/scheduler/scheduler.py`
- Test: `tests/test_scheduler.py`

The current code wraps async tasks in `anyio.from_thread.run()`, which is designed for calling async code from a synchronous thread. `AsyncIOScheduler` runs inside the existing event loop and can schedule coroutine functions directly — the `anyio` wrapper causes a runtime error when the first job fires.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_scheduler.py
import pytest
from unittest.mock import AsyncMock, patch
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import asyncio


def test_scheduler_job_is_coroutine_function():
    """Scheduled jobs must be registered as coroutine functions, not anyio wrappers."""
    import inspect
    from src.scheduler.scheduler import _run_task
    assert inspect.iscoroutinefunction(_run_task), "_run_task must be a coroutine function"


def test_start_scheduler_returns_running_scheduler(tmp_path, monkeypatch):
    """Scheduler starts even when no schedules.yaml exists."""
    from src.scheduler import scheduler as sched_mod
    monkeypatch.setattr(sched_mod, "SCHEDULES_PATH", tmp_path / "schedules.yaml")
    s = sched_mod.start_scheduler()
    assert s.running
    s.shutdown(wait=False)
```

- [ ] **Step 2: Run to confirm second test fails or first test notes the bug**

```bash
uv run pytest tests/test_scheduler.py -v
```

Expected: both tests pass (the first confirms `_run_task` is already a coroutine function — it is; the bug is in `start_scheduler` using `anyio.from_thread.run` as a wrapper, not in `_run_task` itself). Read the current `scheduler.py` to understand what to change.

- [ ] **Step 3: Fix `start_scheduler` in `src/scheduler/scheduler.py`**

Find the job registration block (around line 84). Replace:

```python
scheduler.add_job(
    lambda t=task: anyio.from_thread.run(_run_task, t),
    trigger=trigger,
    id=task["name"],
    replace_existing=True,
)
```

With:

```python
scheduler.add_job(
    _run_task,
    trigger=trigger,
    args=[task],
    id=task["name"],
    replace_existing=True,
)
```

Also remove the `import anyio` line at the top of the file if `anyio` is no longer used anywhere else.

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/test_scheduler.py -v
```

Expected: PASS

- [ ] **Step 5: Run full test suite**

```bash
uv run pytest -v
```

Expected: all green

- [ ] **Step 6: Commit**

```bash
git add src/scheduler/scheduler.py tests/test_scheduler.py
git commit -m "fix: schedule jobs as coroutines directly instead of anyio.from_thread wrapper"
```

---

### Task 6: Create `~/.open-assistant/schedules.yaml`

**Files:**
- Create: `~/.open-assistant/schedules.yaml`
- Create: `tests/test_schedules.py`

You need your Telegram chat ID first. Send `/chatid` to the bot and note the number.

- [ ] **Step 1: Write the failing test**

```python
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
```

- [ ] **Step 2: Run to confirm it fails**

```bash
uv run pytest tests/test_schedules.py -v
```

Expected: FAIL — `schedules.yaml not found`

- [ ] **Step 3: Create `~/.open-assistant/schedules.yaml`**

Replace `YOUR_CHAT_ID` with the number returned by `/chatid`.

```yaml
# Open Assistant — scheduled jobs
# Chat ID obtained via /chatid command in Telegram

tasks:
  - name: morning-briefing
    cron: "0 8 * * 1-5"   # weekdays at 8:00 AM Berlin time
    prompt: >
      Morning briefing. DO NOT write to memory files.
      1. Read ~/.open-assistant/memory/index.md then projects.md, commitments.md, preferences.md, procrastination.md.
      2. Run: gws calendar +agenda
      3. Run: gws gmail +triage
      4. Run: gws tasks tasks list --params '{"tasklist":"@default"}'
      Output a structured morning briefing:
      **Today's 3 priorities** (realistic given the calendar — no more than 3, bold them)
      **Emails needing action** (max 3, one line each with suggested next step)
      **One item to face today** (oldest item in procrastination.md older than 3 days, if any — name it directly)
      Tone: direct, no filler, no emoji. Max 15 lines.
    notify:
      telegram: ["YOUR_CHAT_ID"]

  - name: evening-review
    cron: "30 19 * * *"   # every day at 7:30 PM Berlin time
    prompt: >
      Evening review. DO NOT write to memory files.
      1. Read ~/.open-assistant/memory/projects.md.
      2. Use Bash to get today's start-of-day in Berlin:
         python3 -c "from datetime import datetime; import zoneinfo; tz=zoneinfo.ZoneInfo('Europe/Berlin'); print(datetime.now(tz).replace(hour=0,minute=0,second=0,microsecond=0).isoformat())"
      3. Run: gws tasks tasks list --params '{"tasklist":"@default","showCompleted":true,"completedMin":"<RESULT>"}'
      4. Run: gws calendar +agenda
      Output in 5 lines max:
      - What got done today (completed tasks and attended events)
      - What carries forward to tomorrow
      - One honest reflection question (specific to today, no filler)
    notify:
      telegram: ["YOUR_CHAT_ID"]

  - name: weekly-planning
    cron: "0 17 * * 0"    # Sundays at 5:00 PM Berlin time
    prompt: >
      Weekly planning. DO NOT write to memory files.
      1. Read all files in ~/.open-assistant/memory/.
      2. Use Bash to compute next Monday and Sunday in Europe/Berlin time:
         python3 -c "from datetime import datetime, timedelta; import zoneinfo; tz=zoneinfo.ZoneInfo('Europe/Berlin'); now=datetime.now(tz); offset=now.strftime('%z'); offset=offset[:3]+':'+offset[3:]; today=now.date(); monday=today+timedelta(days=(7-today.weekday())%7 or 7); sunday=monday+timedelta(days=6); print(monday.isoformat()+'T00:00:00'+offset, sunday.isoformat()+'T23:59:59'+offset)"
      3. Run: gws calendar events list --params '{"calendarId":"primary","timeMin":"<MONDAY>","timeMax":"<SUNDAY>","singleEvents":true,"orderBy":"startTime"}'
      4. Run: gws tasks tasks list --params '{"tasklist":"@default"}'
      Output:
      - Days that look overloaded (more than 3 commitments)
      - Missing time for: gym (need at least 3 sessions), family/relationship, piano
      - Suggested time blocks to protect (list only — do NOT create calendar events)
      - One thing to defer if the week is too full
      End with: "Reply here or send /week to finalize and create these blocks."
    notify:
      telegram: ["YOUR_CHAT_ID"]

  - name: midweek-pulse
    cron: "0 12 * * 3"    # Wednesdays at noon Berlin time
    prompt: >
      Midweek pulse. DO NOT write to memory files.
      1. Read ~/.open-assistant/memory/projects.md.
      2. Run: gws tasks tasks list --params '{"tasklist":"@default","showCompleted":true}'
         Use the completed field to assess this week's progress. If completed tasks are not available,
         fall back to reading projects.md for current status.
      Output in 3-4 lines:
      - Status on the main projects (on track / slipping / blocked)
      - One concrete action to do before Friday if anything is off-track
      No emoji, no filler.
    notify:
      telegram: ["YOUR_CHAT_ID"]

  - name: bureaucracy-check
    cron: "0 9 1 * *"     # 1st of every month at 9:00 AM Berlin time
    prompt: >
      Monthly bureaucracy check. DO NOT write to memory files.
      1. Read ~/.open-assistant/memory/german-life.md and commitments.md.
      Surface any deadline, renewal, or required action due in the next 30 days.
      If the baby has arrived (check commitments.md for a birth date), include these German
      post-birth requirements with their exact deadlines:
      - Geburtsurkunde: within 7 days of birth
      - Krankenkasse registration: immediate
      - Kindergeld application: within 6 months
      - Elternzeit notification: 7 weeks before start
      Format as a checklist with exact due dates. If nothing is due in 30 days, say so in one line.
    notify:
      telegram: ["YOUR_CHAT_ID"]
```

- [ ] **Step 4: Run all schedule tests**

```bash
uv run pytest tests/test_schedules.py -v
```

Expected: PASS — all 5 tests green

- [ ] **Step 5: Run the full test suite**

```bash
uv run pytest -v
```

Expected: PASS — all tests green

- [ ] **Step 6: Commit**

```bash
git add tests/test_schedules.py
git commit -m "test: add scheduled jobs structure tests"
# schedules.yaml lives outside the repo — no git commit needed for it
```

---

### Task 6: Bootstrap session — fill memory files

This is a manual conversation step, not code. Run the bot and have the following conversation with it via Telegram.

- [ ] **Step 1: Start the bot**

```bash
uv run open-assistant
```

- [ ] **Step 2: Run the bootstrap conversation**

Send this message to the bot:

> Let's do a memory bootstrap. I want you to ask me structured questions to fill in my memory files. Go through each topic one at a time: (1) current projects and their status, (2) key commitments and deadlines including the baby, (3) my preferences — focus hours, gym schedule, communication style, piano goal, (4) German bureaucracy items I need to track, (5) anything I've been procrastinating. After each topic, write the information to the appropriate memory file before moving to the next. Start with projects.

- [ ] **Step 3: Verify memory files were updated**

```bash
cat ~/.open-assistant/memory/projects.md
cat ~/.open-assistant/memory/commitments.md
cat ~/.open-assistant/memory/preferences.md
cat ~/.open-assistant/memory/german-life.md
cat ~/.open-assistant/memory/procrastination.md
```

All files should contain real content, not just the skeleton comments.

- [ ] **Step 4: Test `/plan` end-to-end**

Send `/plan` in Telegram. Verify the response:
- References your actual projects by name
- Shows today's real calendar events
- Surfaces any emails needing action
- Stays within 15 lines
- Asks "Does this look right?"

- [ ] **Step 5: Test `/avoid`**

Send `/avoid` in Telegram. If procrastination.md has entries, verify they appear with day counts. If empty, manually add one entry to test:

```bash
echo "- [$(date +%Y-%m-%d -d '5 days ago' 2>/dev/null || date -v-5d +%Y-%m-%d) added] Test procrastinated task" >> ~/.open-assistant/memory/procrastination.md
```

Then send `/avoid` again and verify the item appears with age.

---

## Final Verification

- [ ] All tests pass: `uv run pytest -v`
- [ ] `/chatid` returns your numeric chat ID
- [ ] `/plan` reads memory + calendar + email + tasks, proposes ≤3 priorities
- [ ] `/week` reads the full week and suggests time blocks without auto-creating events
- [ ] `/note buy Windeln` adds a task to Google Tasks and confirms
- [ ] `/avoid` surfaces procrastinated items with day counts
- [ ] `/update projects` lets you update project status and writes it to `projects.md`
- [ ] Morning briefing fires at 8:00 AM and appears in Telegram (verify by temporarily setting cron to 1 minute from now, then restoring)
