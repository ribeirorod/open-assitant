# Open Assistant

A personal AI assistant that connects to **Telegram** and **WhatsApp** with full access to your **Google Workspace** — Gmail, Calendar, Drive, Tasks, Docs, and Sheets — powered by [Claude](https://claude.ai).

## What it does

Talk to it naturally from your phone or desktop:

> *"What do I have on today?"*
> *"Summarize my unread emails and flag anything urgent."*
> *"Create a task to follow up with Alice by Friday."*
> *"Draft a reply to the last email from my manager."*

It also runs **scheduled tasks** — morning briefings, weekly summaries, reminders — delivered directly to your chat.

## Architecture

```
┌────────────┐      ┌──────────────┐      ┌────────────┐
│  Telegram   │      │   WhatsApp    │      │  Scheduler  │
│  (polling)  │      │   (Baileys)   │      │   (cron)    │
└──────┬──────┘      └──────┬───────┘      └──────┬──────┘
       │                     │                     │
       └─────────────────────┼─────────────────────┘
                             │
                    ┌────────▼────────┐
                    │   Claude Agent   │  claude-sonnet-4-6
                    │   (Agent SDK)    │  session persistence
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │    gws CLI       │  Google Workspace
                    └─────────────────┘
```

**Two services run in Docker:**

| Service | Stack | Purpose |
|---------|-------|---------|
| `assistant` | Python 3.12 + FastAPI + Claude Agent SDK | Core agent, Telegram bot, scheduler, webhook server |
| `baileys` | Node.js 18 + Baileys | WhatsApp Web bridge (QR-linked, no Meta API needed) |

## Requirements

- [Docker](https://docs.docker.com/get-docker/)
- [Node.js + npm](https://nodejs.org/) — for the Google Workspace CLI
- A [Claude](https://claude.ai) subscription **or** [Anthropic API key](https://console.anthropic.com/)
- A Google account
- A Telegram and/or WhatsApp account

## Quick start

### Option A — CLI wizard (recommended)

```bash
pip install .                     # or: uv pip install .
open-assistant init               # scaffold docker-compose.yaml + .env.example
open-assistant setup              # interactive wizard — walks you through everything
open-assistant start              # build and launch containers
```

The wizard covers channel selection, Telegram bot creation, Google Workspace OAuth, Claude auth, and optional API keys (Groq, OpenAI, Deepgram, Perplexity). Safe to re-run — already-completed steps are skipped.

### Option B — manual

<details>
<summary>Click to expand</summary>

#### 1. Environment variables

```bash
cp .env.example .env
# fill in your values — see .env.example for descriptions
```

#### 2. Google Workspace

```bash
npm install -g @googleworkspace/cli
gws auth setup    # creates a Cloud project and OAuth credentials
gws auth login    # authenticates in your browser
```

#### 3. Claude authentication

**With a Claude subscription:**

```bash
# on any machine with Claude Code installed:
claude setup-token
# then after the container starts:
docker exec -it assistant claude setup-token <token>
```

**With an API key:**

Set `ANTHROPIC_API_KEY=sk-ant-...` in `.env`.

#### 4. Launch

```bash
docker compose up -d --build
docker compose logs -f assistant
```

#### 5. Link WhatsApp

```bash
docker compose logs -f baileys
# scan the QR code: WhatsApp → Settings → Linked Devices → Link a Device
```

</details>

## CLI commands

```
open-assistant init       # create project files in current directory
open-assistant setup      # interactive credential wizard
open-assistant start      # docker compose up --build -d
open-assistant stop       # docker compose down
open-assistant status     # show running containers
open-assistant logs       # stream container logs
```

All commands support `--help`. Non-interactive flags are available on `setup` for scripted/agent-driven installs.

## Channels

### Telegram

- Polling-based bot via [python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot)
- Slash commands: `/plan`, `/week`, `/inbox`, `/note`, `/find`, and more
- Voice message transcription (Groq, OpenAI, or Deepgram)
- Optional user allowlist

### WhatsApp

- Uses [Baileys](https://github.com/WhiskeySockets/Baileys) — a WebSocket-based WhatsApp Web client
- No Meta Cloud API or business account needed — links like a second phone
- Supports text, images, audio, video, stickers, polls, and reactions
- QR code pairing on first run, session persisted to a Docker volume

## Scheduled tasks

Create `~/.open-assistant/schedules.yaml`:

```yaml
tasks:
  - name: morning-briefing
    cron: "0 8 * * 0-4"           # weekdays at 8 am (0=Mon in APScheduler)
    prompt: >
      Give me a morning briefing: unread emails, today's calendar,
      and any overdue tasks.
    notify:
      telegram: ["123456789"]     # your Telegram chat ID

  - name: weekly-wrap
    cron: "0 17 * * 4"            # Fridays at 5 pm
    prompt: "Summarize this week's calendar and flag important emails."
    notify:
      telegram: ["123456789"]
      whatsapp: ["15551234567"]   # E.164 format
```

Changes take effect without restarting the container.

## Project structure

```
src/
├── main.py                  # Entrypoint — runs all services concurrently
├── config.py                # Settings from environment (pydantic)
├── agent/
│   ├── core.py              # Claude Agent SDK client + session pool
│   └── session_store.py     # File-backed session persistence
├── channels/
│   ├── telegram.py          # Telegram bot (polling + commands)
│   ├── telegram_notify.py   # Outbound Telegram for scheduled tasks
│   └── whatsapp.py          # WhatsApp webhook (FastAPI router)
├── scheduler/
│   └── scheduler.py         # APScheduler cron engine
├── memory/
│   └── sync.py              # Bi-directional Google Drive memory sync
└── tools/                   # Custom MCP tool stubs

open_assistant/
├── cli.py                   # Typer CLI — init, setup, start, stop, logs
└── wizard.py                # Interactive setup wizard

baileys-bridge/
├── index.js                 # Baileys + Express WhatsApp bridge
├── Dockerfile               # Node.js 18 container
└── package.json
```

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

[MIT](LICENSE)
