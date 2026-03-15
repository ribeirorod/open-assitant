# Design: Apple Notes, Apple Reminders & Skills Architecture Cleanup

**Date:** 2026-03-15
**Status:** Approved

---

## Problem

The project has two competing skill systems:

- `src/skills/*.md` — flat markdown files loaded by `telegram.py` for slash commands
- `.claude/skills/*/SKILL.md` — structured skill files used by Claude Code CLI and, via `setting_sources=["project"]`, by the running bot agent

The `SYSTEM_PROMPT` in `core.py` also embeds tool documentation (gws commands, memory instructions) that does not belong there — it should state purpose, limits, and guardrails only. Skills are auto-discoverable by the SDK.

---

## Goals

1. Establish `.claude/skills/` as the single source of truth for all skills
2. Slim `SYSTEM_PROMPT` to purpose + guardrails only
3. Rewire Telegram slash commands to load from `.claude/skills/`
4. Add Apple Notes and Apple Reminders as new skills
5. Delete `src/skills/`

---

## Architecture

### Skill Discovery

The Claude Agent SDK reads `.claude/` when `setting_sources=["project"]` is set (already configured in `core.py`). Skills in `.claude/skills/<name>/SKILL.md` are automatically available to the agent. The agent uses the `Skill` tool (already in `allowed_tools`) to load and follow a skill's instructions when relevant.

No explicit skill listing is needed in `SYSTEM_PROMPT`. The agent discovers skills from the `description` field in each skill's YAML frontmatter.

### Skill File Format

```
---
name: <skill-name>
description: <one-line description — this is what the agent uses to decide when to invoke the skill>
---

# Skill Title
...instructions...
```

All skills live at: `.claude/skills/<name>/SKILL.md`

---

## Changes

### 1. `SYSTEM_PROMPT` in `src/agent/core.py`

**Remove:** all gws command references, memory protocol instructions, planning discipline section, procrastination protocol section.

**Keep / rewrite as:**

```
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
```

**Update `tests/test_core_prompt.py`:** all existing assertions reference content being removed. Replace with tests that verify:
- `"DO NOT write to memory"` is present (scheduled job guard)
- `"ambiguous"` is present (confirm-on-ambiguity guardrail)
- `"confirm"` is present (action confirmation guardrail)
- `"Skill"` is present (skill discovery instruction)
- `"gws"` is NOT present (no tool documentation in prompt)

### 2. Telegram skill loading — `src/channels/telegram.py`

**Current:**
```python
_SKILLS_DIR = pathlib.Path(__file__).parent.parent / "skills"

def _skill(name: str, **kwargs: str) -> str:
    text = (_SKILLS_DIR / f"{name}.md").read_text()
    return text.format(**kwargs) if kwargs else text
```

**New:**
```python
# telegram.py is at src/channels/telegram.py
# .parent → src/channels, .parent → src, .parent → project root
_SKILLS_DIR = pathlib.Path(__file__).parent.parent.parent / ".claude" / "skills"

def _skill(name: str, **kwargs: str) -> str:
    text = (_SKILLS_DIR / name / "SKILL.md").read_text()
    # SKILL.md files may contain raw JSON with curly braces — do NOT use str.format().
    # Append user args as a separate line instead.
    if kwargs.get("args"):
        text = text + f"\n\nUser input: {kwargs['args']}"
    return text
```

**Important:** The old `_skill()` used `str.format(**kwargs)` which relied on `{args}` placeholders in the skill body. SKILL.md files contain JSON examples with curly braces that will raise `KeyError` with `str.format()`. The new implementation appends user input as a suffix instead. This is a deliberate UX change for `/note`, `/update`, `/project`, `/memory` — the skill instructions remain clean and user text arrives as a postfix.

No changes to command handlers — `/plan`, `/note`, `/week`, etc. all continue to work.

**Runtime dependency:** `setting_sources=["project"]` in `ClaudeAgentOptions` resolves `.claude/` relative to the process working directory. The app must be run from the project root (e.g. `uv run python -m src.main` from `/path/to/open-assitant`). To make this deterministic regardless of cwd, add `cwd=str(Path(__file__).parent.parent)` to `ClaudeAgentOptions` in `_build_options()`. This is a required change, not optional.

**Handler divergence note:** The `_memory` and `_project` handlers in `telegram.py` (lines 169, 174) already append args directly in the handler body and never pass kwargs to `_skill()`. They are unaffected by the `_skill()` rewrite. Only `/note` (`_note`) and `/update` (`_update`) pass `args` as kwargs — these are the only two handlers that exercise the new `kwargs.get("args")` path.

### 3. Delete `src/skills/`

Remove the directory and all `.md` files inside it. Content is already present in `.claude/skills/`.

### 4. New skill: `.claude/skills/apple-notes/SKILL.md`

Provides `memo` CLI instructions for managing Apple Notes. macOS-only. Covers: list, search, create, edit, delete, move, export.

Skill must include an availability check: before any `memo` command, verify with `command -v memo` and return a clear error if not installed.

Prerequisite (verify current command at https://github.com/antoniorodr/memo before writing):
```
brew tap antoniorodr/memo && brew install memo
```

### 5. New skill: `.claude/skills/apple-reminders/SKILL.md`

Provides `remindctl` CLI instructions for managing Apple Reminders. macOS-only. Covers: list (today/week/overdue), add with due dates, complete, delete, list management.

Includes disambiguation: if the user says "remind me" but context suggests an in-chat alert (not Apple Reminders), ask which they mean before acting.

Skill must include an availability check: before any `remindctl` command, verify with `command -v remindctl` and return a clear error if not installed.

Prerequisite (verify current command at https://github.com/steipete/remindctl before writing):
```
brew install steipete/tap/remindctl
```

**Docker / Linux note:** Both skills are macOS-only. The Docker deployment (`Dockerfile` uses `python:3.12-slim`) does not support them. The availability check in each skill ensures graceful failure with a clear message rather than a cryptic `command not found` error.

---

## Data Flow

```
User message (Telegram / any channel)
        │
        ▼
ask_agent() → ClaudeSDKClient
        │
        ├─ SDK reads .claude/skills/ descriptions at startup (setting_sources=["project"])
        │
        ├─ Agent reasons: "this needs apple-notes skill"
        │
        ├─ Agent calls Skill tool: skill("apple-notes")
        │
        ├─ Agent runs: Bash("memo notes -a 'dentist Thursday'")
        │
        └─ Agent confirms with user if ambiguous, then executes
```

---

## Out of Scope

- Migrating existing skill content (plan, note, week, etc.) — files already exist in `.claude/skills/`, this is just about fixing the loader
- WhatsApp integration — tracked in GitHub issue #1
- Skills system for non-macOS environments

---

## Verification

**Skills wiring**
- [ ] `/plan` Telegram command still works after `_SKILLS_DIR` change
- [ ] `/note some text` passes "User input: some text" appended to skill body (no `str.format()` crash)
- [ ] `src/skills/` directory no longer exists

**Agent behaviour**
- [ ] Agent responds to "add a note: X" by invoking `memo` CLI
- [ ] Agent responds to "remind me to X tomorrow" by invoking `remindctl`
- [ ] Agent asks for confirmation before writing note or reminder
- [ ] Agent asks clarifying question when request is ambiguous (e.g. "remind me" with no date)
- [ ] Agent returns a clear error (not a stack trace) when `memo` or `remindctl` is not installed

**System prompt**
- [ ] `SYSTEM_PROMPT` contains no `gws` command references
- [ ] `SYSTEM_PROMPT` contains `"DO NOT write to memory"` (scheduled job guard)
- [ ] `tests/test_core_prompt.py` updated and passing

**Runtime**
- [ ] App started from project root resolves `.claude/skills/` correctly
- [ ] `ClaudeAgentOptions` in `_build_options()` has explicit `cwd=str(Path(__file__).parent.parent)` set to project root for deterministic skill discovery
