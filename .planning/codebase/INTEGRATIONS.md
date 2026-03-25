# External Integrations

**Analysis Date:** 2026-03-25

## APIs & Services

| Service | Purpose | SDK/Client | Auth (env var) |
|---------|---------|------------|----------------|
| Anthropic Claude (via Claude Code CLI) | Core AI reasoning & tool use | `claude-agent-sdk` + `claude` CLI | OAuth token stored in `claude-auth` Docker volume; `ANTHROPIC_API_KEY` intentionally unset in compose |
| Telegram Bot API | User-facing chat channel (polling) | `python-telegram-bot` | `OA_TELEGRAM_BOT_TOKEN` |
| WhatsApp (via Baileys) | User-facing chat channel (webhook) | `@whiskeysockets/baileys` (Node sidecar) + `httpx` (Python) | QR-code link; session in `baileys-auth` volume |
| Google Drive | Memory file sync (bi-directional) | `gws` CLI (`@googleworkspace/cli`) | OAuth via `gws-auth` volume + `gws-creds.json` |
| Google Workspace (Calendar, Gmail, Tasks) | Email, calendar, task management via skills | `gws` CLI | Same OAuth as Drive |
| Groq (Whisper) | Speech-to-text (primary STT) | `groq` Python SDK | `GROQ_API_KEY` |
| OpenAI (Whisper + TTS) | STT fallback + text-to-speech | `openai` Python SDK | `OPENAI_API_KEY` |
| Deepgram Nova-2 | STT fallback (tertiary) | Direct `httpx` REST call | `DEEPGRAM_API_KEY` |
| Perplexity | Web search via MCP | `server-perplexity-ask` (npx MCP stdio server) | `PERPLEXITY_API_KEY` |

---

## Integration Details

### Claude Agent SDK / Claude Code CLI
- **How it works:** `src/agent/core.py` maintains one `ClaudeSDKClient` per `chat_id` in a process-level dict (`_clients`). Each client wraps a persistent Claude Code CLI subprocess. `client.query()` sends a user message; `client.receive_response()` streams back `AssistantMessage` / `ResultMessage` objects. Sessions survive process restarts: the `session_id` is written to `~/.open-assistant/sessions/<chat_id>.json` and passed as `resume=` on next startup.
- **Model:** Configured via `OA_CLAUDE_MODEL` (default `claude-sonnet-4-6`).
- **Tools available to agent:** `Bash`, `Read`, `Write`, `WebSearch`, `WebFetch`, `Skill`, `mcp__perplexity-ask__perplexity_ask`.
- **MCP server:** `perplexity-ask` launched as a stdio subprocess (`npx -y server-perplexity-ask`) with `PERPLEXITY_API_KEY` injected.
- **Auth:** OAuth token stored in the `claude-auth` Docker volume at `/root/.claude`. The container entrypoint (`entrypoint.sh`) restores `/root/.claude.json` from a backup if missing. `ANTHROPIC_API_KEY` is explicitly blanked in `docker-compose.yaml` to force OAuth path.
- **Files:** `src/agent/core.py`, `src/agent/session_store.py`, `.claude/settings.json`

---

### Telegram
- **How it works:** Long-polling via `python-telegram-bot`. `build_telegram_app()` in `src/channels/telegram.py` registers command handlers (`/plan`, `/week`, `/note`, `/avoid`, `/update`, `/calibration`, `/memory`, `/project`, `/find`, `/inbox`, `/reset`, `/chatid`) and message handlers for text and voice/audio. Each handler calls `ask_agent(prompt, chat_id)` and replies with MarkdownV2 (converted via `telegramify-markdown`). Long messages are split at paragraph boundaries.
- **Voice handling:** Voice/audio files are downloaded via Bot API, then transcribed using STT providers in priority order: Groq Whisper → OpenAI Whisper → Deepgram. The transcript is forwarded to the agent as text.
- **Outbound notifications (scheduler):** `src/channels/telegram_notify.py` uses raw `httpx` POST to `https://api.telegram.org/bot{token}/sendMessage` — no Application lifecycle needed.
- **Auth:** Bot token set via `OA_TELEGRAM_BOT_TOKEN`. Optional user allowlist via `OA_TELEGRAM_ALLOWED_USERS`.
- **Files:** `src/channels/telegram.py`, `src/channels/telegram_notify.py`

---

### WhatsApp (Baileys Bridge)
- **Architecture:** Two-service design. The `baileys` Docker service runs a Node.js Express server (`baileys-bridge/index.js`) that maintains the WhatsApp Web socket connection. Inbound messages are forwarded via HTTP POST to `http://assistant:8080/webhook/whatsapp/baileys`. Outbound messages are sent by the Python app via HTTP POST to `http://baileys:3100/send/text` (and other endpoints).
- **How inbound works:** Baileys emits `messages.upsert` events → normalises to a JSON payload (id, from, type, text, media, quotedMessage) → POSTs to Python webhook → `src/channels/whatsapp.py` `inbound_from_bridge()` → `ask_agent()` → `send_text()` back to bridge.
- **Outbound API surface (bridge endpoints):**
  - `POST /send/text` — text messages (with optional quote)
  - `POST /send/media` — image, video, audio, document
  - `POST /send/sticker` — sticker
  - `POST /send/poll` — polls
  - `POST /react` — reactions (add/remove)
  - `POST /edit` — edit sent message
  - `POST /unsend` — delete sent message
  - `POST /group/create|rename|description|participants|invite-code|revoke-invite|leave|icon`
  - `GET /group/info/:groupId`
- **Auth:** QR code printed to terminal on first run; multi-device session stored in `baileys-auth` Docker volume at `/app/auth_state`. No API keys required.
- **ACK message:** Optional instant acknowledgement message configurable via `BAILEYS_ACK_MESSAGE` env var (sent immediately on inbound, before agent response).
- **Files:** `baileys-bridge/index.js`, `src/channels/whatsapp.py`, `docker-compose.yaml`

---

### Google Workspace (Calendar, Gmail, Tasks, Drive)
- **How it works:** The agent shell-execs the `gws` CLI (`@googleworkspace/cli`) as a subprocess. Skills in `.claude/skills/` (e.g. `plan`, `inbox`, `week`, `pulse`) contain exact `gws` CLI commands for the agent to run. Memory sync (`src/memory/sync.py`) uses `gws drive files list/get/create/update` commands directly for bi-directional GDrive file sync at startup and on demand.
- **Memory sync flow:** On startup (`src/main.py`) → `memory_pull()` → compares remote `modifiedTime` vs local sync metadata (`~/.open-assistant/memory/.sync-meta.json`) → downloads only changed files. Push uploads local `.md` files that are newer or absent on remote.
- **GDrive folder:** `open_assistant/memory/` created automatically if absent.
- **Auth:** OAuth credentials via `gws auth login` (interactive, run once inside container). Token persisted in `gws-auth` Docker volume at `/root/.config/gws`. Plain credentials file bind-mounted from host at path hardcoded in gws config (`gws-creds.json`).
- **Files:** `src/memory/sync.py`, `src/config.py` (`gws_binary` setting), `.claude/skills/plan/`, `.claude/skills/inbox/`, `.claude/skills/week/`, `.claude/skills/pulse/`

---

### Groq (Whisper STT)
- **How it works:** `groq.AsyncGroq` client instantiated in `src/channels/telegram.py` if `GROQ_API_KEY` is set. Called first in the STT provider chain via `_transcribe_groq()`. Uses model `whisper-large-v3-turbo` with `response_format="text"`.
- **Auth:** `GROQ_API_KEY` environment variable (no `OA_` prefix).
- **Files:** `src/channels/telegram.py`

---

### OpenAI (Whisper STT + TTS)
- **STT:** `openai.AsyncOpenAI` used as second fallback via `_transcribe_openai()`. Model `whisper-1`.
- **TTS:** `_synthesize()` uses `tts-1` model, voice `alloy`, format `opus` (OGG/Opus for Telegram voice). TTS is implemented but voice replies are suppressed per `feedback_audio_response.md` — agent always responds with text.
- **Auth:** `OPENAI_API_KEY` environment variable (no `OA_` prefix).
- **Files:** `src/channels/telegram.py`

---

### Deepgram (STT fallback)
- **How it works:** Third in STT fallback chain. Called via direct `httpx.AsyncClient.post()` to `https://api.deepgram.com/v1/listen?model=nova-2&smart_format=true`. No SDK used.
- **Auth:** `DEEPGRAM_API_KEY` environment variable. Passed as `Authorization: Token <key>` header.
- **Files:** `src/channels/telegram.py` (`_transcribe_deepgram()`)

---

### Perplexity (Web Search via MCP)
- **How it works:** Registered as an MCP stdio server in `src/agent/core.py`. Launched as `npx -y server-perplexity-ask` when the Claude agent connects. Exposed to the agent as the tool `mcp__perplexity-ask__perplexity_ask`.
- **Auth:** `PERPLEXITY_API_KEY` injected into the MCP subprocess environment.
- **Files:** `src/agent/core.py` (`_MCP_SERVERS` dict)

---

## Data Storage

- **Sessions:** Local JSON files at `~/.open-assistant/sessions/<chat_id>.json` (bind-mounted from host). Managed by `src/agent/session_store.py`.
- **Schedules:** `~/.open-assistant/schedules.yaml` (YAML cron config, bind-mounted from host). Read by `src/scheduler/scheduler.py`.
- **Memory files:** `~/.open-assistant/memory/*.md` (bind-mounted from host). Synced to/from GDrive by `src/memory/sync.py`.
- **File storage:** No dedicated object storage. Media files referenced by local path when sent via Baileys bridge.
- **Caching:** None.

---

## Webhooks

- **Incoming:** `POST /webhook/whatsapp/baileys` — receives normalised WhatsApp messages from the Baileys sidecar. Registered in `src/channels/whatsapp.py`. Exposed on port 8080 (`OA_WEBHOOK_PORT`).
- **Outgoing:** None. Baileys bridge calls Python via the callback URL `http://assistant:8080/webhook/whatsapp/baileys` (set via `BAILEYS_CALLBACK_URL` env var in docker-compose).

---

## Required Environment Variables

| Variable | Service | Required |
|----------|---------|----------|
| `OA_TELEGRAM_BOT_TOKEN` | Telegram | Yes (Telegram channel disabled if absent) |
| `OA_TELEGRAM_ALLOWED_USERS` | Telegram allowlist | No (open if empty) |
| `GROQ_API_KEY` | Groq STT | No (STT falls back to OpenAI/Deepgram) |
| `OPENAI_API_KEY` | OpenAI STT + TTS | No (STT falls back to Deepgram) |
| `DEEPGRAM_API_KEY` | Deepgram STT | No (tertiary fallback) |
| `PERPLEXITY_API_KEY` | Perplexity MCP web search | No (tool unavailable if absent) |
| `OA_CLAUDE_MODEL` | Claude model selection | No (defaults to `claude-sonnet-4-6`) |
| `OA_BAILEYS_BRIDGE_URL` | WhatsApp bridge URL | No (defaults to `http://localhost:3100`) |
| `OA_WEBHOOK_PORT` | FastAPI port | No (defaults to `8080`) |
| `BAILEYS_ACK_MESSAGE` | Instant WA acknowledgement | No (disabled if empty) |
