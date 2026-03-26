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

```bash
./setup.sh
```

The setup script will walk you through everything: installing dependencies, creating your Telegram bot, authenticating with Google Workspace, setting up Claude, and launching the stack.

> **Requirements:** Docker Desktop, Node.js (for the `gws` CLI), and a Claude Code installation on any machine.

> **Note:** Run all commands from the repo root directory. The setup script must be run as `./setup.sh` from within the cloned repository.

---

## Manual setup

<details>
<summary>Advanced users — expand for manual steps</summary>

### 1. Copy and fill in environment variables

```bash
cp .env.example .env
```

Edit `.env` and fill in your values. See `.env.example` for descriptions of each variable.

### 2. Authenticate with Google Workspace

```bash
npm install -g @googleworkspace/cli
gws auth login
```

This stores OAuth tokens at `~/.config/gws`, which the container reads at runtime.

### 3. Authenticate with Claude

**Option A — setup-token (recommended):**

On any machine with Claude Code installed and authenticated:
```bash
claude setup-token
```

After starting the container:
```bash
docker exec assistant claude setup-token <your-token>
```

**Option B — API key:**

Set `ANTHROPIC_API_KEY` in your `.env` file.

### 4. Launch

```bash
docker compose up --build
```

### 5. Link WhatsApp (if using WhatsApp)

```bash
docker compose logs -f baileys
```

Scan the QR code with WhatsApp → Settings → Linked Devices → Link a Device.

</details>

## Channels

### Telegram

1. Create a bot via [@BotFather](https://t.me/BotFather).
2. Set `OA_TELEGRAM_BOT_TOKEN` in `.env`.
3. Optionally restrict access with `OA_TELEGRAM_ALLOWED_USERS`.

### WhatsApp

WhatsApp is supported via the [Baileys](https://github.com/WhiskeySockets/Baileys) bridge (WhatsApp Web protocol). No Meta developer account is needed — setup is done by scanning a QR code during `./setup.sh`.

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
│   └── whatsapp.py          # WhatsApp Baileys bridge (FastAPI router)
├── scheduler/
│   └── scheduler.py         # APScheduler cron jobs
└── tools/                   # (extensible) custom MCP tools
```

## License

MIT
