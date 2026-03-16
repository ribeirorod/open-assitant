# Apple Notes, Reminders & Skills Architecture Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Establish `.claude/skills/` as the single skill source, slim the agent's SYSTEM_PROMPT to purpose + guardrails only, rewire Telegram slash commands to the unified skill directory, and add Apple Notes and Apple Reminders as auto-discoverable skills.

**Architecture:** Skills live in `.claude/skills/<name>/SKILL.md` and are auto-discovered by the Claude Agent SDK via `setting_sources=["project"]`. The agent uses the `Skill` tool to load skill instructions on demand. The Telegram bot loads the same files for slash command prompts via a fixed path resolver.

**Tech Stack:** Python 3.11, python-telegram-bot, claude_agent_sdk, `memo` CLI (Apple Notes), `remindctl` CLI (Apple Reminders), pytest, uv

---

## File Map

| File | Action | Responsibility |
|------|--------|---------------|
| `tests/test_core_prompt.py` | Modify | Assert new lean SYSTEM_PROMPT shape |
| `src/agent/core.py` | Modify | Lean SYSTEM_PROMPT + deterministic `cwd` in `_build_options()` |
| `tests/test_skill_loader.py` | Create | Unit tests for `_skill()` path resolution and args handling |
| `src/channels/telegram.py` | Modify | Rewire `_SKILLS_DIR` + rewrite `_skill()` |
| `src/skills/` | Delete | Obsolete directory |
| `.claude/skills/apple-notes/SKILL.md` | Create | `memo` CLI instructions for agent |
| `.claude/skills/apple-reminders/SKILL.md` | Create | `remindctl` CLI instructions for agent |

---

## Chunk 1: Core Infrastructure

### Task 1: Rewrite `test_core_prompt.py` to reflect the new SYSTEM_PROMPT

The new SYSTEM_PROMPT removes all tool documentation. Write the new tests first — they will fail until Task 2 is done.

**Files:**
- Modify: `tests/test_core_prompt.py`

- [ ] **Step 1: Replace the entire file with new assertions**

```python
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
```

- [ ] **Step 2: Run the tests — verify the right ones fail**

```bash
cd /path/to/open-assitant && uv run pytest tests/test_core_prompt.py -v
```

Expected: **3 tests FAIL, 2 tests PASS**. The current SYSTEM_PROMPT already contains `"DO NOT write to memory"` and `"confirm"`, so those two pass immediately. The three that must fail are:
- `test_system_prompt_has_ambiguity_guardrail` — `"ambiguous"` not present yet
- `test_system_prompt_references_skill_tool` — `"Skill"` not present yet
- `test_system_prompt_has_no_tool_documentation` — `"gws"` still present

If anything other than these three fails, investigate before proceeding.

- [ ] **Step 3: Commit the failing tests**

```bash
git add tests/test_core_prompt.py
git commit -m "test: rewrite test_core_prompt.py for lean system prompt"
```

---

### Task 2: Rewrite `SYSTEM_PROMPT` and fix `cwd` in `core.py`

**Files:**
- Modify: `src/agent/core.py`

- [ ] **Step 1: Replace `SYSTEM_PROMPT`**

Open `src/agent/core.py`. Find the `SYSTEM_PROMPT = """\` block (lines ~32–82) and replace the entire string with:

```python
SYSTEM_PROMPT = """\
You are Open Assistant — a personal life organiser and Google Workspace helper.

You run on macOS. You have access to tools: Bash, Read, Write, WebSearch, WebFetch, Skill, and MCP servers.

SKILLS
Before acting on any request, invoke the relevant Skill to load full instructions for that capability.
Available skills are in .claude/skills/ and discovered automatically.

SCHEDULED JOBS
When a prompt begins with "DO NOT write to memory" — obey that instruction exactly and skip all memory writes.

GUARDRAILS
- Always confirm before sending emails, creating calendar events, modifying tasks, or writing/deleting notes and reminders. One short sentence: "Ready — confirm?"
- When a request is ambiguous, ask one clarifying question before acting. Never assume intent.
- Never auto-create, auto-send, or auto-delete anything.

FORMATTING
- Responses render as Markdown in Telegram.
- Use **bold** for labels, bullet lists for structured data, `inline code` for IDs/dates/filenames.
- Default to 3–6 lines. Max 5 list items then summarise ("…and 3 more").
- No emoji. No greetings. No filler phrases.
"""
```

- [ ] **Step 2: Fix `cwd` in `_build_options()`**

`core.py` lives at `src/agent/core.py`. Project root is three `.parent` steps up. Find `_build_options()` and add `cwd`:

```python
# Add this import at the top of core.py — it is NOT currently present:
from pathlib import Path

# In _build_options(), update ClaudeAgentOptions:
def _build_options(resume_session_id: str | None = None) -> ClaudeAgentOptions:
    # core.py is at src/agent/core.py → .parent=src/agent → .parent=src → .parent=project root
    _PROJECT_ROOT = str(Path(__file__).parent.parent.parent)
    opts = ClaudeAgentOptions(
        system_prompt=SYSTEM_PROMPT,
        allowed_tools=["Bash", "Read", "Write", "WebSearch", "WebFetch", "Skill", "mcp__perplexity-ask__perplexity_ask"],
        mcp_servers=_MCP_SERVERS,
        setting_sources=["project"],
        model=settings.claude_model,
        max_turns=15,
        cwd=_PROJECT_ROOT,
    )
    if resume_session_id:
        opts.resume = resume_session_id
    return opts
```

> **Note:** The spec says `parent.parent` but that resolves to `src/` — not project root. `parent.parent.parent` is the correct path from `src/agent/core.py`.

- [ ] **Step 3: Run the prompt tests — verify they all PASS**

```bash
uv run pytest tests/test_core_prompt.py -v
```

Expected: all 5 tests PASS.

- [ ] **Step 4: Run full test suite to catch regressions**

```bash
uv run pytest --tb=short -q
```

Expected: no new failures introduced.

- [ ] **Step 5: Commit**

```bash
git add src/agent/core.py
git commit -m "refactor: slim SYSTEM_PROMPT to purpose/guardrails, fix cwd for skill discovery"
```

---

### Task 3: Write tests for `_skill()` then rewire Telegram skill loader

**Files:**
- Create: `tests/test_skill_loader.py`
- Modify: `src/channels/telegram.py`

- [ ] **Step 1: Write failing tests for the new `_skill()` behaviour**

```python
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
```

- [ ] **Step 2: Run tests — verify they FAIL**

```bash
uv run pytest tests/test_skill_loader.py -v
```

Expected: `test_skills_dir_points_to_claude_skills` fails (still pointing at `src/skills`), others may pass or fail.

- [ ] **Step 3: Rewrite `_skill()` and `_SKILLS_DIR` in `telegram.py`**

Open `src/channels/telegram.py`. Keep `import pathlib` at line 7 unchanged. Replace only lines 10–16 (the `_SKILLS_DIR` assignment and `_skill()` function):

```python
# telegram.py is at src/channels/telegram.py
# .parent → src/channels  .parent → src  .parent → project root
_SKILLS_DIR = pathlib.Path(__file__).parent.parent.parent / ".claude" / "skills"


def _skill(name: str, **kwargs: str) -> str:
    """Load a skill from .claude/skills/<name>/SKILL.md.

    User args are appended as a suffix — never injected via str.format(),
    because SKILL.md files contain JSON with curly braces that would crash it.
    """
    text = (_SKILLS_DIR / name / "SKILL.md").read_text()
    if kwargs.get("args"):
        text = text + f"\n\nUser input: {kwargs['args']}"
    return text
```

- [ ] **Step 4: Run skill loader tests — verify they PASS**

```bash
uv run pytest tests/test_skill_loader.py -v
```

Expected: all 4 tests PASS.

- [ ] **Step 5: Run full test suite**

```bash
uv run pytest --tb=short -q
```

Expected: no failures.

- [ ] **Step 6: Commit**

```bash
git add tests/test_skill_loader.py src/channels/telegram.py
git commit -m "refactor: rewire _skill() loader to .claude/skills/ directory"
```

---

## Chunk 2: Content

### Task 4: Delete `src/skills/`

Content is already present in `.claude/skills/`. This directory is now dead code.

**Files:**
- Delete: `src/skills/` (entire directory)

- [ ] **Step 1: Verify no imports reference it**

```bash
grep -r "src/skills\|src.*skills" src/ tests/ --include="*.py"
```

Expected: no matches.

- [ ] **Step 2: Run full test suite before deletion**

```bash
uv run pytest --tb=short -q
```

Expected: all tests pass.

- [ ] **Step 3: Remove and commit**

```bash
git rm -r src/skills/
git commit -m "chore: remove obsolete src/skills/ directory"
```

---

### Task 5: Add Apple Notes skill

**Files:**
- Create: `.claude/skills/apple-notes/SKILL.md`

- [ ] **Step 1: Verify the `memo` install command at the upstream repo**

Before writing the skill, check https://github.com/antoniorodr/memo for the current Homebrew install command. The formula name may differ from `antoniorodr/memo/memo`.

- [ ] **Step 2: Create the skill file**

```bash
mkdir -p .claude/skills/apple-notes
```

Write `.claude/skills/apple-notes/SKILL.md`:

```markdown
---
name: apple-notes
description: Manage Apple Notes — create, search, list, and export notes via the memo CLI. Use when the user mentions notes, Apple Notes, or asks to jot something down.
---

# Apple Notes

Manage Apple Notes via the `memo` CLI on macOS.

## Availability check

Before any command, verify memo is installed:

```bash
command -v memo || echo "memo not installed — run: brew tap antoniorodr/memo && brew install antoniorodr/memo/memo"
```

If not installed, tell the user and stop.

## Confirmation

Always confirm with the user before creating a note. One sentence: "Ready to [action] — confirm?"

## Commands

**List all notes**
```bash
memo notes
```

**Filter by folder**
```bash
memo notes -f "Folder Name"
```

**Search notes (interactive fuzzy search)**
```bash
memo notes -s
```
Note: `-s` launches interactive fuzzy search — no inline query string is supported.

**Create a note (interactive)**
```bash
memo notes -a
```
Note: `-a` opens an interactive editor. It does not accept a title argument on the command line.

**Export to HTML/Markdown (interactive)**
```bash
memo notes -ex
```

## Limitations — Bot context

The following commands are interactive and require terminal input. **Never run them directly in bot context.** Instead, tell the user to run them manually in a terminal:

- `memo notes -e` — edit a note
- `memo notes -d` — delete a note
- `memo notes -m` — move note to folder
- `memo notes -a` — create a note (interactive editor)
- `memo notes -s` — search (interactive fuzzy)

For bot-triggered note creation, inform the user that `memo` requires interactive input and suggest they run it in a terminal.

## Other limitations

- Cannot edit notes that contain images or attachments.
- macOS only. Requires Notes.app and Automation permission (System Settings → Privacy & Security → Automation).
```

- [ ] **Step 3: Commit**

```bash
git add .claude/skills/apple-notes/SKILL.md
git commit -m "feat: add apple-notes skill via memo CLI"
```

---

### Task 6: Add Apple Reminders skill

**Files:**
- Create: `.claude/skills/apple-reminders/SKILL.md`

- [ ] **Step 1: Verify the `remindctl` install command**

Before writing the skill, check https://github.com/steipete/remindctl for the current Homebrew install command.

- [ ] **Step 2: Create the skill file**

```bash
mkdir -p .claude/skills/apple-reminders
```

Write `.claude/skills/apple-reminders/SKILL.md`:

```markdown
---
name: apple-reminders
description: Manage Apple Reminders — list, add, complete, and delete reminders via remindctl CLI. Use when the user mentions reminders, the Reminders app, or asks to be reminded of something with a due date synced to iPhone.
---

# Apple Reminders

Manage Apple Reminders via the `remindctl` CLI on macOS.

## Availability and permissions check

Before any command, verify remindctl is installed and authorised:

```bash
command -v remindctl || echo "remindctl not installed — run: brew install steipete/tap/remindctl"
remindctl status
```

If not installed or not authorised, tell the user and stop. To grant permission: `remindctl authorize`

## Disambiguation

If the user says "remind me" and the intent is ambiguous — no due date, or context suggests an in-chat alert rather than the Reminders app — ask:

> "Do you want this in Apple Reminders (syncs to your iPhone) or as a one-off message from me here?"

Only proceed once the intent is clear.

## Confirmation

Always confirm before creating, completing, or deleting a reminder. One sentence: "Ready to [action] — confirm?"

## Commands

**Check permissions**
```bash
remindctl status
```

**Today's reminders**
```bash
remindctl today
```

**Tomorrow**
```bash
remindctl tomorrow
```

**This week**
```bash
remindctl week
```

**Overdue**
```bash
remindctl overdue
```

**All reminders**
```bash
remindctl all
```

**List all lists**
```bash
remindctl list
```

**Add a reminder**
```bash
remindctl add --title "Task title" --list "List Name" --due "YYYY-MM-DD HH:mm"
```

Accepted due formats: `today`, `tomorrow`, `YYYY-MM-DD`, `YYYY-MM-DD HH:mm`, ISO 8601

**Edit a reminder**
```bash
remindctl edit <id> --title "New title" --due "YYYY-MM-DD HH:mm"
```

**Complete one or more reminders by ID**
```bash
remindctl complete <id1> <id2> <id3>
```

IDs come from the output of listing commands (hex format, e.g. `4A83`). Multiple IDs accepted in one call.

**Delete a reminder**
```bash
remindctl delete <id> --force
```

IDs come from listing output (hex format, e.g. `4A83`) — do not invent integer IDs.

**JSON output (for scripting)**
```bash
remindctl today --json
```

## Notes

- macOS only. Requires Reminders.app and permission (`remindctl authorize` on first use, `remindctl status` to check).
- IDs are hex identifiers shown in listing output — always retrieve them from `remindctl` output, never guess.
```

- [ ] **Step 3: Commit**

```bash
git add .claude/skills/apple-reminders/SKILL.md
git commit -m "feat: add apple-reminders skill via remindctl CLI"
```

---

## Final Verification

Run through the spec's checklist before declaring done:

- [ ] `uv run pytest --tb=short -q` — all tests pass
- [ ] `/plan` works: `_skill("plan")` reads `.claude/skills/plan/SKILL.md`
- [ ] `/note buy milk` works: skill content + `"\n\nUser input: buy milk"` appended, no crash
- [ ] `src/skills/` no longer exists: `ls src/skills/` returns error
- [ ] `SYSTEM_PROMPT` has no `gws` references: `grep "gws" src/agent/core.py` returns nothing in the prompt string
- [ ] `SYSTEM_PROMPT` contains `"DO NOT write to memory"`
- [ ] `.claude/skills/apple-notes/SKILL.md` exists and contains `command -v memo`
- [ ] `.claude/skills/apple-reminders/SKILL.md` exists and contains `command -v remindctl`
- [ ] `_build_options()` sets `cwd` to project root (`parent.parent.parent` from `core.py`)
