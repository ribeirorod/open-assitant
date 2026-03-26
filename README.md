# Open Assistant

A personal AI assistant that lives in **Telegram** or **WhatsApp** and has full access to your Google Workspace — email, calendar, Drive, tasks, Docs, and Sheets — powered by [Claude](https://claude.ai).

---

## What it can do

Ask it anything, naturally:

> *"What do I have on today?"*
> *"Summarize my unread emails and flag anything urgent."*
> *"Create a task to follow up with Alice by Friday."*
> *"Draft a reply to the last email from my manager."*

It also runs on a schedule — morning briefings, weekly summaries, reminders — delivered directly to your chat.

---

## Requirements

- [Docker](https://docs.docker.com/get-docker/) — runs the assistant stack
- [Node.js + npm](https://nodejs.org/en/download) — for the Google Workspace CLI
- A [Claude](https://claude.ai) subscription **or** [Anthropic API key](https://console.anthropic.com/)
- A Google account (Gmail, Calendar, Drive, etc.)
- A Telegram and/or WhatsApp account

---

## Setup

```bash
git clone -b public https://github.com/ribeirorod/open-assitant.git open-assistant
cd open-assistant
./setup.sh
```

The script is a fully interactive CLI — it walks you through every step with styled menus, masked token entry, and inline editing. No manual config file editing required.

**What it covers:**

1. Verifies Docker is running and installs missing dependencies
2. Channel selection — Telegram, WhatsApp, or both
3. Telegram bot creation — step-by-step instructions via @BotFather
4. Google Workspace authentication — browser OAuth flow, fully guided
5. Claude authentication — subscription token or API key
6. Optional API keys — voice transcription (Groq / OpenAI / Deepgram) and web search (Perplexity)
7. Writes a ready-to-use `.env` file

> **Safe to re-run.** Already-completed steps are skipped and previously entered values are pre-filled — just press Enter to keep them.

**Once setup is complete, launch the stack:**

```bash
docker compose up -d --build
```

View logs:

```bash
docker compose logs -f assistant
```

---

## Scheduled tasks

Create `~/.open-assistant/schedules.yaml`:

```yaml
tasks:
  - name: morning-briefing
    cron: "0 8 * * 1-5"           # weekdays at 8 am
    prompt: >
      Give me a morning briefing: unread emails (flag anything urgent),
      today's calendar, and any overdue tasks.
    notify:
      telegram: ["123456789"]     # your Telegram chat ID

  - name: weekly-wrap
    cron: "0 17 * * 5"            # Fridays at 5 pm
    prompt: "Summarize this week's calendar and flag important emails."
    notify:
      telegram: ["123456789"]
      whatsapp: ["15551234567"]   # E.164 format
```

Changes take effect without restarting the container.

---

## Manual setup

<details>
<summary>For advanced users who prefer to configure things by hand</summary>

### 1. Environment variables

```bash
cp .env.example .env
# fill in your values — see .env.example for descriptions
```

### 2. Google Workspace

```bash
npm install -g @googleworkspace/cli
gws auth setup    # creates a Cloud project and OAuth credentials
gws auth login    # authenticates in your browser
```

### 3. Claude authentication

**Option A — setup-token (uses your Claude subscription):**

On any machine with Claude Code installed and logged in:
```bash
claude setup-token
```
After the container starts:
```bash
docker exec -it assistant claude setup-token <token>
```

**Option B — API key:**

Set `ANTHROPIC_API_KEY=sk-ant-...` in `.env`.

### 4. Launch

```bash
docker compose up -d --build
docker compose logs -f assistant
```

### 5. Link WhatsApp (if using WhatsApp)

```bash
docker compose logs -f baileys
# scan the QR code: WhatsApp → Settings → Linked Devices → Link a Device
```

</details>

---

## License

MIT
