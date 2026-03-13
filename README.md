# Open Assistant

Google Workspace assistant accessible via **Telegram** and **WhatsApp**, powered by [Claude Agent SDK](https://github.com/anthropics/claude-code-sdk-python) and the [Google Workspace CLI (`gws`)](https://github.com/googleworkspace/cli).

## Architecture

```
┌────────────┐      ┌────────────┐
│  Telegram   │      │  WhatsApp   │
│  (polling)  │      │ (webhook)   │
└──────┬──────┘      └──────┬──────┘
       │                     │
       └──────────┬──────────┘
                  │
          ┌───────▼────────┐
          │  Claude Agent   │  claude-sonnet-4-6
          │  (Agent SDK)    │  session persistence + auto-compact
          └───────┬────────┘
                  │  Bash tool
          ┌───────▼────────┐
          │   gws CLI       │  Gmail, Calendar, Drive, Sheets, Docs, Tasks …
          └────────────────┘
```

**Two workflows:**

1. **Interactive** — User sends a message on Telegram/WhatsApp → Claude processes it using `gws` → reply goes back to the user.
2. **Scheduled** — Cron tasks run on a schedule → Claude queries Google Workspace → results pushed to Telegram/WhatsApp.

## Quick start

### Prerequisites

- Python 3.10+
- [uv](https://docs.astral.sh/uv/) (fast Python package manager)
- [Google Workspace CLI](https://github.com/googleworkspace/cli): `npm install -g @googleworkspace/cli`
- Anthropic API key

### Install

```bash
uv sync
```

### Configure

```bash
cp .env.example .env
# Fill in your tokens and keys
```

Authenticate with Google Workspace:

```bash
gws auth login
```

### Run

```bash
uv run python -m src.main
```

Or with Docker:

```bash
docker compose up --build
```

## Channels

### Telegram

1. Create a bot via [@BotFather](https://t.me/BotFather).
2. Set `OA_TELEGRAM_BOT_TOKEN` in `.env`.
3. Optionally restrict access with `OA_TELEGRAM_ALLOWED_USERS`.

### WhatsApp (Meta Cloud API)

1. Create a Meta Developer app with the WhatsApp product.
2. Set `OA_WHATSAPP_ACCESS_TOKEN`, `OA_WHATSAPP_PHONE_NUMBER_ID`, and `OA_WHATSAPP_VERIFY_TOKEN`.
3. Configure the webhook URL in Meta dashboard: `https://<your-host>:8080/webhook/whatsapp`.

## Scheduled tasks

Create `~/.open-assistant/schedules.yaml`:

```yaml
tasks:
  - name: morning-briefing
    cron: "0 8 * * 1-5"
    prompt: "Give me a morning briefing: unread emails, today's calendar, and pending tasks."
    notify:
      telegram: ["123456789"]
      whatsapp: ["15551234567"]

  - name: weekly-report
    cron: "0 17 * * 5"
    prompt: "Summarize this week's calendar events and any flagged emails."
    notify:
      telegram: ["123456789"]
```

## Project structure

```
src/
├── main.py                  # Entrypoint — runs all services
├── config.py                # Settings from environment
├── agent/
│   ├── core.py              # Claude Agent SDK integration
│   └── session_store.py     # File-backed session persistence
├── channels/
│   ├── telegram.py          # Telegram bot (python-telegram-bot)
│   ├── telegram_notify.py   # Outbound Telegram for scheduler
│   └── whatsapp.py          # WhatsApp Cloud API (FastAPI router)
├── scheduler/
│   └── scheduler.py         # APScheduler cron jobs
└── tools/                   # (extensible) custom MCP tools
```

## License

MIT
