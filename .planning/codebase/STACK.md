# Technology Stack

**Analysis Date:** 2026-03-25

## Languages
- **Primary:** Python 3.12 — application logic, agent core, channels, scheduler, memory sync
- **Secondary:** JavaScript (ES Modules, Node.js 20) — WhatsApp Baileys bridge sidecar (`baileys-bridge/index.js`)
- **Shell:** POSIX sh — container entrypoint (`entrypoint.sh`)

## Runtime & Package Manager
- **Python:** 3.12-slim (Docker base image)
- **Package manager:** pip with `requirements.txt` — no lockfile (lock not committed)
- **Node.js:** 20-slim (Docker base image for sidecar)
- **Package manager:** npm with `baileys-bridge/package.json` — `package-lock.json` not committed

## Frameworks

| Framework | Version | Purpose |
|-----------|---------|---------|
| FastAPI | >=0.115 | Webhook server for WhatsApp inbound messages |
| uvicorn | >=0.34 | ASGI server running FastAPI (`src/main.py`) |
| python-telegram-bot | >=21.0 | Telegram bot (polling mode, `src/channels/telegram.py`) |
| APScheduler | >=3.10 | Cron-style scheduled tasks (`src/scheduler/scheduler.py`) |
| Express | ^4.21.2 | REST API inside the Baileys Node.js sidecar (`baileys-bridge/index.js`) |

## Key Dependencies

| Package | Version | Why Critical |
|---------|---------|--------------|
| `claude-agent-sdk` | >=0.1.48 | Core AI engine — wraps Claude Code CLI for multi-turn agentic sessions |
| `@whiskeysockets/baileys` | ^6.7.16 | WhatsApp Web protocol client; entire WA integration depends on it |
| `pydantic` / `pydantic-settings` | >=2.0 | Settings validation via `src/config.py`; env-var prefix `OA_` |
| `groq` | >=0.11.0 | Whisper STT (primary transcription provider) |
| `openai` | >=2.28.0 | Whisper STT (fallback) and TTS (OpenAI `tts-1`) |
| `httpx` | >=0.27 | Async HTTP — Baileys bridge calls, Deepgram STT, Telegram notify |
| `anyio` | >=4.0 | Async primitives underpinning SDK and httpx |
| `pyyaml` | >=6.0 | Parsing `~/.open-assistant/schedules.yaml` |
| `telegramify-markdown` | >=1.0.0 | Converts plain Markdown to Telegram MarkdownV2 before sending |
| `pino` | ^9.6.0 | Structured logging in the Node.js sidecar |
| `qrcode-terminal` | ^0.12.0 | Prints WA QR code to terminal on first link |

## Configuration

- **Environment:** All settings loaded via `src/config.py` (`pydantic-settings`, `env_prefix="OA_"`, `.env` file support).
  Key env vars:
  - `OA_TELEGRAM_BOT_TOKEN` — Telegram bot credentials
  - `OA_TELEGRAM_ALLOWED_USERS` — comma-separated allowlist
  - `OA_BAILEYS_BRIDGE_URL` — internal URL of the Node sidecar (default `http://localhost:3100`)
  - `OA_WEBHOOK_HOST` / `OA_WEBHOOK_PORT` — FastAPI binding (default `0.0.0.0:8080`)
  - `OA_CLAUDE_MODEL` — Claude model ID (default `claude-sonnet-4-6`)
  - `GROQ_API_KEY`, `OPENAI_API_KEY`, `DEEPGRAM_API_KEY` — STT/TTS providers (no `OA_` prefix)
  - `PERPLEXITY_API_KEY` — Perplexity MCP server
- **Build:** No build step for Python. Node sidecar: `npm install --omit=dev` in `baileys-bridge/Dockerfile`.
- **Claude tools/permissions:** `.claude/settings.json` — defines allowed/denied Bash and file-system permissions for the agent.

## Platform Requirements

- **Development:** Docker + Docker Compose (`docker-compose.yaml`). Two services: `assistant` (Python) and `baileys` (Node.js).
- **Production:** Same Docker Compose stack. Port `8080` (assistant webhook) and `3100` (Baileys bridge) exposed. Three named Docker volumes:
  - `claude-auth` — Claude Code OAuth session (`/root/.claude`)
  - `gws-auth` — Google Workspace CLI OAuth (`/root/.config/gws`)
  - `baileys-auth` — WhatsApp multi-device auth state (`/app/auth_state`)
- **Bind mounts (host):**
  - `/Users/beam/.open-assistant` → `/root/.open-assistant` — schedules, sessions, memory
  - `/Users/beam/open-assitant/gws-creds.json` — GWS OAuth credentials (read-only)
  - `/Users/beam/projects`, `/Users/beam/Downloads`, `/Users/beam/Documents` — read-only filesystem access for the `find` skill
- **Global CLIs installed in container image:**
  - `@googleworkspace/cli` (`gws`) — Google Workspace operations
  - `@anthropic-ai/claude-code` — Claude Code CLI (agent backend)
