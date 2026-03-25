# Codebase Structure

**Analysis Date:** 2026-03-25

## Directory Layout

```
open-assitant/
├── src/                          # Python application source
│   ├── main.py                   # Application entrypoint — starts all subsystems
│   ├── config.py                 # Pydantic Settings; all env var definitions
│   ├── agent/
│   │   ├── core.py               # ClaudeSDKClient pool, ask_agent(), session resume
│   │   └── session_store.py      # JSON files: chat_id → Claude session_id
│   ├── channels/
│   │   ├── telegram.py           # python-telegram-bot: polling, commands, STT
│   │   ├── telegram_notify.py    # Outbound-only Telegram via raw Bot API (scheduler use)
│   │   └── whatsapp.py           # FastAPI router: inbound webhook + Baileys REST client
│   ├── memory/
│   │   └── sync.py               # GDrive pull/push/sync via gws CLI
│   └── scheduler/
│       └── scheduler.py          # APScheduler: loads schedules.yaml, runs cron tasks
│
├── baileys-bridge/               # Node.js WhatsApp Web sidecar service
│   ├── index.js                  # Express server + Baileys WebSocket client
│   ├── package.json
│   └── Dockerfile
│
├── .claude/
│   ├── settings.json             # Claude Code tool permissions
│   └── skills/                   # Agent skill definitions (Markdown)
│       ├── apple-notes/SKILL.md
│       ├── apple-reminders/SKILL.md
│       ├── avoid/SKILL.md        # Review commitments to avoid over-scheduling
│       ├── calibration/SKILL.md
│       ├── find/SKILL.md         # File search across mounted Mac directories
│       ├── inbox/SKILL.md        # Gmail triage workflow
│       ├── memory/SKILL.md       # Memory read/write/archive + GDrive sync instructions
│       ├── note/SKILL.md         # Quick note capture
│       ├── plan/SKILL.md         # Daily planning (calendar + email + tasks)
│       ├── project/SKILL.md      # Project status read/update
│       ├── pulse/SKILL.md        # Scheduled email/calendar pulse check
│       ├── update/SKILL.md       # Update a topic in memory
│       ├── week/SKILL.md         # Weekly review workflow
│       └── whatsapp/SKILL.md     # Full Baileys bridge API reference + curl examples
│
├── tests/                        # pytest test suite
│   ├── test_core_prompt.py
│   ├── test_memory.py
│   ├── test_memory_sync.py
│   ├── test_missed_message.py
│   ├── test_scheduler.py
│   ├── test_schedules.py
│   ├── test_skill_loader.py
│   └── test_telegram_commands.py
│
├── docs/
│   └── superpowers/              # Design specs and plans
│       ├── plans/
│       └── specs/
│
├── cli.py                        # Interactive REPL / one-shot CLI (dev/debug use)
├── schedules.example.yaml        # Template for ~/.open-assistant/schedules.yaml
├── Dockerfile                    # Python 3.12 + Node + gws + claude-code
├── docker-compose.yaml           # assistant + baileys services
├── entrypoint.sh                 # Docker entrypoint: seeds memory, syncs settings
├── pyproject.toml                # Project metadata, dependencies, ruff + pytest config
├── requirements.txt              # Pinned deps (generated from pyproject.toml)
└── uv.lock                       # uv lockfile
```

---

## Directory Purposes

| Directory | Purpose | Contains | Key Files |
|-----------|---------|----------|-----------|
| `src/` | Main Python application | All Python modules | `main.py`, `config.py` |
| `src/agent/` | AI agent session management | Claude SDK integration | `core.py`, `session_store.py` |
| `src/channels/` | Messaging channel adapters | Telegram + WhatsApp integration | `telegram.py`, `whatsapp.py`, `telegram_notify.py` |
| `src/memory/` | Memory sync | GDrive pull/push logic | `sync.py` |
| `src/scheduler/` | Cron-driven proactive tasks | APScheduler setup | `scheduler.py` |
| `baileys-bridge/` | WhatsApp Web protocol sidecar | Node.js Express + Baileys | `index.js` |
| `.claude/skills/` | Agent skill definitions | Markdown SKILL.md files | One subdirectory per skill |
| `tests/` | Test suite | pytest files | `test_*.py` |
| `docs/superpowers/` | Design documents | Specs and plans | Not source code |

---

## Runtime Data Directories (outside project root, created at runtime)

| Path | Purpose | Notes |
|------|---------|-------|
| `~/.open-assistant/sessions/` | Session ID map per chat_id | Written by `session_store.py`; bind-mounted from `/Users/beam/.open-assistant` |
| `~/.open-assistant/memory/` | Active memory files (`.md`) | Synced from/to GDrive; read by the agent via the `Read` tool |
| `~/.open-assistant/schedules.yaml` | User-defined cron tasks | Loaded at startup; edit and restart to apply |
| `~/.claude/projects/` | Claude SDK full conversation transcripts | Managed by Claude Code; Docker volume `claude-auth` |

---

## Where to Add New Code

| What | Location | Notes |
|------|----------|-------|
| New Telegram command | `src/channels/telegram.py` | Add handler function + register with `CommandHandler` in `build_telegram_app()` |
| New skill | `.claude/skills/<skill-name>/SKILL.md` | YAML frontmatter `name` + `description` at top; agent discovers automatically |
| New scheduled task | `~/.open-assistant/schedules.yaml` | YAML entry with `name`, `cron`, `prompt`, `notify`; no code changes needed |
| New config variable | `src/config.py` | Add field to `Settings`; use `OA_` prefix unless it's a third-party key |
| New WhatsApp outbound helper | `src/channels/whatsapp.py` | Add async function using `_bridge_post()` |
| New memory sync operation | `src/memory/sync.py` | Follow the `async def` pattern using `_run_gws()` |
| New test | `tests/` | Name file `test_<module>.py`; use `pytest-asyncio` for async tests |

---

## Naming Conventions

- **Files:** `snake_case.py` — Example: `session_store.py`, `telegram_notify.py`
- **Directories:** `snake_case` — Example: `baileys-bridge/` is the exception (Node convention)
- **Skill directories:** `kebab-case` — Example: `apple-notes/`, `apple-reminders/`
- **Python functions:** `snake_case`; private helpers prefixed with `_` — Example: `_bridge_post`, `_run_task`
- **Docker env vars / config keys:** `SCREAMING_SNAKE_CASE` with `OA_` prefix — Example: `OA_TELEGRAM_BOT_TOKEN`

---

## Special Directories

| Directory | Purpose | Generated | Committed |
|-----------|---------|-----------|-----------|
| `.venv/` | Python virtual environment | Yes (uv/venv) | No |
| `.pytest_cache/` | pytest cache | Yes | No |
| `src/__pycache__/` | Python bytecode | Yes | No |
| `.planning/codebase/` | Architecture analysis docs | Yes (by map-codebase) | Optional |
| `.claude/` | Claude Code settings + skills | Partially (settings.json committed, sessions not) | Yes (skills + settings) |
| `baileys-bridge/` | Separate Node.js service | No | Yes |
| `docs/` | Design documents | No | Yes |
