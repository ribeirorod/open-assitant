# Architecture

**Analysis Date:** 2026-03-25

## Pattern Overview

- **Overall:** Multi-channel chatbot with a central AI agent core, following a Channel → Agent → Tool pattern
- **Key characteristics:**
  - Two inbound channels (Telegram polling, WhatsApp webhook) both funnel to a single `ask_agent()` function
  - The agent is a long-lived `ClaudeSDKClient` per chat session — not stateless, not request/response
  - Skills are plain Markdown files in `.claude/skills/` and are injected as prompt context at the call site, not hardcoded in the system prompt
  - All scheduled proactive tasks use one unified YAML + APScheduler pattern; they go through the same `ask_agent()` path and fan-out to channels
  - Memory is a two-tier system: local files under `~/.open-assistant/memory/` and Google Drive as the durable backing store, synced via the `gws` CLI
  - WhatsApp connectivity requires a Node.js sidecar service (`baileys-bridge`) that bridges the WhatsApp Web protocol to a REST API

---

## Layers

**Channel Layer:**
- Purpose: Accept inbound messages from Telegram or WhatsApp, extract text, route to the agent, return the formatted reply
- Location: `src/channels/`
- Contains: `telegram.py` (python-telegram-bot Application, polling), `whatsapp.py` (FastAPI router, webhook), `telegram_notify.py` (outbound-only, scheduler use)
- Depends on: `src/agent/core.py`, `src/config.py`
- Used by: `src/main.py` (mounts/starts both channels)

**Agent Core Layer:**
- Purpose: Maintain one `ClaudeSDKClient` per `chat_id`, handle session resume across process restarts, and expose a single `ask_agent(text, chat_id) → str` function
- Location: `src/agent/`
- Contains: `core.py` (client pool, query/response loop, session persistence), `session_store.py` (JSON files at `~/.open-assistant/sessions/`)
- Depends on: `claude_agent_sdk`, `src/config.py`
- Used by: `src/channels/telegram.py`, `src/channels/whatsapp.py`, `src/scheduler/scheduler.py`

**Scheduler Layer:**
- Purpose: Run cron-driven proactive tasks that query the agent and fan-out replies to configured Telegram/WhatsApp recipients
- Location: `src/scheduler/`
- Contains: `scheduler.py` (APScheduler AsyncIOScheduler, loads `~/.open-assistant/schedules.yaml`)
- Depends on: `src/agent/core.py`, `src/channels/telegram_notify.py`, `src/channels/whatsapp.py`
- Used by: `src/main.py`

**Memory Sync Layer:**
- Purpose: Pull memory files from Google Drive to local disk on startup; push updated files back after writes
- Location: `src/memory/`
- Contains: `sync.py` (async pull/push/sync using `gws drive` CLI subcommands, last-write-wins conflict resolution)
- Depends on: `src/config.py`, the `gws` CLI binary
- Used by: `src/main.py` (startup pull), skill-invoked pushes at runtime

**Configuration Layer:**
- Purpose: Single `Settings` object loading all env vars with `OA_` prefix (plus a few without prefix for third-party keys)
- Location: `src/config.py`
- Contains: Pydantic `BaseSettings` singleton `settings`
- Used by: every other layer

**Baileys Bridge (Sidecar):**
- Purpose: Implement the WhatsApp Web protocol (multi-device, signal encryption) — something Python cannot do natively
- Location: `baileys-bridge/` (separate Node.js service)
- Contains: `index.js` — Express HTTP server + `@whiskeysockets/baileys` WebSocket client
- Communicates with the Python app via two HTTP calls:
  - Inbound: bridge POSTs to `http://assistant:8080/webhook/whatsapp/baileys`
  - Outbound: Python POSTs to `http://baileys:3100/send/text` (and other endpoints)

---

## Data Flow

**Telegram inbound message:**
1. User sends message → Telegram servers → `telegram.py:_handle_message` (via python-telegram-bot long polling)
2. `_is_allowed()` checks `OA_TELEGRAM_ALLOWED_USERS`; stale messages (>300 s) are replied to with a missed-message prompt and dropped
3. `ask_agent(text, chat_id=str(tg_chat_id))` is called
4. `core.py:_get_or_create_client()` loads session from `~/.open-assistant/sessions/<chat_id>.json`, calls `ClaudeSDKClient.connect()` with optional `resume=session_id`
5. `client.query(text)` sends the message; `client.receive_response()` streams back `AssistantMessage` / `ResultMessage` objects
6. The new `session_id` is persisted to disk via `session_store.save_session()`
7. Response text is converted to MarkdownV2 via `telegramify_markdown.markdownify()` and sent in chunks (max 4090 chars each)

**Telegram voice/audio message:**
1. `telegram.py:_handle_voice` downloads OGG bytes via Telegram Bot API
2. STT cascade: Groq Whisper → OpenAI Whisper → Deepgram (first success wins)
3. Transcript text is forwarded through the same `ask_agent()` → reply path as text messages
4. Always replies with text (never TTS audio)

**WhatsApp inbound message:**
1. User sends message → WhatsApp servers → Baileys WebSocket → `baileys-bridge/index.js:messages.upsert` handler
2. Bridge normalises message into a JSON payload `{id, from, type, text, ...}` and POSTs to `http://assistant:8080/webhook/whatsapp/baileys`
3. `whatsapp.py:inbound_from_bridge()` receives the webhook; non-text types are ignored (return `"ignored"`)
4. `ask_agent(text, chat_id="wa:<jid>")` is called — the `wa:` prefix namespaces the session from Telegram sessions
5. Response is sent back via `send_text(sender, response, quoted_id=msg_id)` → POST to Baileys bridge `/send/text`

**Scheduler proactive task:**
1. `start_scheduler()` reads `~/.open-assistant/schedules.yaml` at startup; registers one APScheduler job per task
2. At cron time, `_run_task(task)` calls `ask_agent(prompt, chat_id="sched:<task_name>")`
3. Empty responses are swallowed (no notification sent)
4. Non-empty responses fan out: for each Telegram ID → `telegram_notify.send_telegram_message()`; for each WhatsApp number → `whatsapp.send_notification()`

**Memory sync:**
1. On startup: `memory.sync.pull()` runs; for each file in the GDrive `open_assistant/memory/` folder, if `modifiedTime > last_synced` the file is downloaded to `~/.open-assistant/memory/`
2. After agent writes a memory file: the agent (via skill instructions in `memory/SKILL.md`) calls `python -c "... from src.memory.sync import push; asyncio.run(push(['FILE.md']))"` directly as a Bash command
3. `push()` uploads changed `.md` files to GDrive; updates `~/.open-assistant/memory/.sync-meta.json` with timestamps

---

## Key Abstractions

| Abstraction | Purpose | Location | Pattern |
|-------------|---------|----------|---------|
| `ask_agent(text, chat_id)` | Universal entry point for all messages to the AI | `src/agent/core.py` | Async function, returns `str` |
| `ClaudeSDKClient` pool (`_clients`) | One live session per chat_id, reused across requests | `src/agent/core.py` | In-memory dict; resumed from disk on restart |
| Session store | Maps `chat_id → session_id` for cross-restart resume | `src/agent/session_store.py` | JSON files at `~/.open-assistant/sessions/` |
| Skills | Agent capabilities as plain Markdown; injected as the user prompt | `.claude/skills/<name>/SKILL.md` | Loaded by `_skill(name)` in `telegram.py`; discoverable by `Skill` tool |
| `Settings` | All configuration from env vars | `src/config.py` | Pydantic `BaseSettings` singleton; env prefix `OA_` |
| Baileys bridge | WhatsApp Web protocol adapter | `baileys-bridge/index.js` | Separate Docker service; communicates over HTTP |

---

## Entry Points

| Entry Point | Location | Triggers |
|-------------|----------|----------|
| Production server | `src/main.py:main()` | `python -m src.main` or `open-assistant` CLI script |
| Interactive REPL / one-shot CLI | `cli.py` | `python cli.py [message]` — uses `chat_id="cli-session"` |
| WhatsApp webhook | `src/channels/whatsapp.py` → `POST /webhook/whatsapp/baileys` | HTTP POST from Baileys bridge |
| Telegram polling | `src/channels/telegram.py:build_telegram_app()` | Started in `main.py` if `OA_TELEGRAM_BOT_TOKEN` is set |

---

## Error Handling

- **Strategy:** Log-and-continue. No crashes propagate to the user if avoidable.
- **Patterns:**
  - Telegram: `_handle_error` global handler replies "Something went wrong."
  - WhatsApp webhook: HTTP 200 returned regardless; errors are logged
  - Session resume: if `ClaudeSDKClient.connect()` fails with a resume ID, the session ID is cleared and a fresh connection is attempted
  - Memory pull failure at startup: logged as warning, app continues with local files
  - STT failure: falls through the provider cascade; if all fail, replies "No speech detected"
  - Missed Telegram messages (>300 s old): replied to with a softened prompt, not forwarded to the agent

---

## Cross-Cutting Concerns

- **Logging:** `logging.basicConfig` at `INFO` level in `src/main.py`; each module gets `log = logging.getLogger(__name__)`
- **Validation:** Pydantic `BaseSettings` for config only; request bodies from Telegram/Baileys are plain dicts with `.get()` access
- **Authentication:**
  - Telegram: username allowlist (`OA_TELEGRAM_ALLOWED_USERS`); empty = open
  - WhatsApp: no auth on the webhook (assumed internal Docker network only)
  - Claude Agent SDK: OAuth via `claude-auth` Docker volume (`ANTHROPIC_API_KEY` is intentionally unset)
  - Google Workspace: `gws` CLI OAuth via `gws-auth` Docker volume
  - Baileys: QR-code pairing on first run; session persisted to `baileys-auth` Docker volume
- **Concurrency:** Everything runs in a single asyncio event loop; `asyncio.gather` runs Uvicorn server and Telegram polling concurrently
