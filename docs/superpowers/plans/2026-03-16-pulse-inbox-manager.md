# Pulse & Inbox Manager Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add hourly background email surveillance (pulse) with spam rescue, and a weekly inbox manager skill for user-confirmed cleanup, both wired into the existing YAML scheduler.

**Architecture:** Two new `.claude/skills/` files drive all intelligence. One small Python change adds an empty-response guard to `scheduler.py` so silent pulse runs don't send empty Telegram messages. One Telegram command (`/inbox`) is added following the exact pattern of every other command in `telegram.py`. No new Python modules.

**Tech Stack:** Python 3.11, APScheduler, python-telegram-bot, `gws` CLI (Gmail), pytest + pytest-asyncio, Claude Agent SDK

---

## Chunk 1: Python infrastructure (scheduler guard + /inbox command)

### Task 1: Scheduler empty-response guard

**Files:**
- Modify: `src/scheduler/scheduler.py` (around line 56 — after `ask_agent` call, before fan-out)
- Modify: `tests/test_scheduler.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_scheduler.py`:

```python
@pytest.mark.asyncio
async def test_run_task_skips_notification_on_empty_response():
    """_run_task must not call send_telegram_message when agent returns empty string."""
    task = {
        "name": "pulse",
        "prompt": "Run the /pulse skill.",
        "notify": {"telegram": ["123456789"]},
    }
    # send_telegram_message is imported lazily inside _run_task, so patch at the source module
    with patch("src.scheduler.scheduler.ask_agent", new=AsyncMock(return_value="")), \
         patch("src.channels.telegram_notify.send_telegram_message", new=AsyncMock()) as mock_send:
        from src.scheduler import scheduler as sched_mod
        await sched_mod._run_task(task)
        mock_send.assert_not_awaited()


@pytest.mark.asyncio
async def test_run_task_sends_notification_on_non_empty_response():
    """_run_task must call send_telegram_message when agent returns content."""
    task = {
        "name": "morning-briefing",
        "prompt": "Give me a briefing.",
        "notify": {"telegram": ["123456789"]},
    }
    with patch("src.scheduler.scheduler.ask_agent", new=AsyncMock(return_value="1. Check email")), \
         patch("src.channels.telegram_notify.send_telegram_message", new=AsyncMock()) as mock_send:
        from src.scheduler import scheduler as sched_mod
        await sched_mod._run_task(task)
        mock_send.assert_awaited_once_with("123456789", "1. Check email")
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /Users/beam/open-assitant && python -m pytest tests/test_scheduler.py::test_run_task_skips_notification_on_empty_response tests/test_scheduler.py::test_run_task_sends_notification_on_non_empty_response -v
```

Expected: FAIL — the guard doesn't exist yet, so the empty-string case will call `send_telegram_message`.

- [ ] **Step 3: Add the empty-response guard to `_run_task`**

In `src/scheduler/scheduler.py`, insert exactly these 3 lines after line 55 (`response = await ask_agent(...)`) and before line 57 (`# Fan out to channels`). Do not change anything else in the function:

```python
    # Silent tasks (e.g. pulse with no notable emails) return empty string — skip fan-out
    if not response or not response.strip():
        log.info("scheduler: task %s returned empty response — no notifications sent", name)
        return
```

The result should look like:

```python
    response = await ask_agent(prompt, chat_id=f"sched:{name}")

    # Silent tasks (e.g. pulse with no notable emails) return empty string — skip fan-out
    if not response or not response.strip():
        log.info("scheduler: task %s returned empty response — no notifications sent", name)
        return

    # Fan out to channels
    notify = task.get("notify", {})
    tg_ids = notify.get("telegram", [])
    ...
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd /Users/beam/open-assitant && python -m pytest tests/test_scheduler.py -v
```

Expected: all pass, including the two new tests.

- [ ] **Step 5: Commit**

```bash
cd /Users/beam/open-assitant
git add src/scheduler/scheduler.py tests/test_scheduler.py
git commit -m "feat: skip fan-out when scheduled task returns empty response"
```

---

### Task 2: `/inbox` Telegram command

**Files:**
- Modify: `src/channels/telegram.py`
- Modify: `tests/test_telegram_commands.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_telegram_commands.py`:

```python
def test_inbox_command_registered(tg_app):
    cmds = _registered_commands(tg_app)
    assert "inbox" in cmds, "/inbox command not registered in Telegram app"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /Users/beam/open-assitant && python -m pytest tests/test_telegram_commands.py::test_inbox_command_registered -v
```

Expected: FAIL — `inbox` is not yet registered.

- [ ] **Step 3: Add `_inbox` handler to `src/channels/telegram.py`**

After the `_find` handler (around line 191), add:

```python
async def _inbox(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await _dispatch(update, _skill("inbox"))
```

Then in `build_telegram_app()`, insert after `app.add_handler(CommandHandler("find", _find))` (around line 395) and **before** the `MessageHandler` lines:

```python
    app.add_handler(CommandHandler("inbox", _inbox))
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd /Users/beam/open-assitant && python -m pytest tests/test_telegram_commands.py -v
```

Expected: all pass.

- [ ] **Step 5: Run full test suite to check for regressions**

```bash
cd /Users/beam/open-assitant && python -m pytest -v
```

Expected: all pass.

- [ ] **Step 6: Commit**

```bash
cd /Users/beam/open-assitant
git add src/channels/telegram.py tests/test_telegram_commands.py
git commit -m "feat: add /inbox Telegram command for inbox manager skill"
```

---

## Chunk 2: Skills and configuration

### Task 3: Pulse skill

**Files:**
- Create: `.claude/skills/pulse/SKILL.md`

- [ ] **Step 1: Create the skill file**

Create `.claude/skills/pulse/SKILL.md` with this exact content:

```markdown
# Pulse Skill

You are running the hourly background email surveillance pulse.

CONSTRAINTS:
- DO NOT write to any memory file other than ~/.open-assistant/memory/pulse-log.md.
- DO NOT write to email-prefs.md (read-only for pulse).
- Return an empty string if nothing is notable — do NOT send any message.
- Do NOT greet the user. Do NOT add filler text.

## Step 1: Get last successful run timestamp

Read ~/.open-assistant/memory/pulse-log.md with the Read tool.

Extract the `last_successful_run:` value from the first few lines. Apply this fallback chain:
- Valid, parseable ISO 8601 timestamp **with timezone offset** → convert to Unix epoch
- Timestamp present but lacking timezone offset (naive) → treat as malformed, use 24 hours ago
- File does not exist → use 24 hours ago; you will create it at the end of this run
- Timestamp absent, malformed, or unparseable → use 24 hours ago
- Timestamp is in the future (clock skew or DST edge) → use 24 hours ago
- Timestamp is older than 24 hours → cap to 24 hours ago

Using 24 hours (not 1 hour) as the fallback ensures overnight and weekend emails are caught on the first run after any gap — including the Monday 8am run after a Friday 6pm close.

Compute the Unix epoch for the Gmail query:

```bash
python3 -c "
from datetime import datetime, timedelta
import zoneinfo

tz = zoneinfo.ZoneInfo('Europe/Berlin')
now = datetime.now(tz)

# Replace the string below with the ISO timestamp you read from pulse-log.md
ts = '<ISO_TIMESTAMP_FROM_FILE>'
try:
    dt = datetime.fromisoformat(ts)
    # Reject naive timestamps (no tzinfo means no offset — treat as malformed)
    if dt.tzinfo is None:
        raise ValueError('naive timestamp')
    # Cap to 24h ago if too old
    if (now - dt).total_seconds() > 86400:
        dt = now - timedelta(hours=24)
    # If in the future, use 24h fallback
    if dt > now:
        dt = now - timedelta(hours=24)
except Exception:
    dt = now - timedelta(hours=24)

print(int(dt.timestamp()))
"
```

Record the fallback timestamp used (needed for the log entry in Step 6).

## Step 2: Read email preferences

Read ~/.open-assistant/memory/email-prefs.md with the Read tool.

If the file does not exist, proceed with empty blocked/trusted lists. You will create it at the end of a successful run.

## Step 3: Query inbox (emails since last_successful_run)

```bash
gws gmail users messages list --params '{"q":"in:inbox after:<UNIX_EPOCH>","maxResults":50}'
```

For each message ID returned, fetch metadata:

```bash
gws gmail users messages get --params '{"id":"<MESSAGE_ID>","format":"metadata","metadataHeaders":["From","Subject","Date"]}'
```

## Step 4: Query SPAM (fixed 24h window)

```bash
gws gmail users messages list --params '{"q":"in:spam newer_than:1d","maxResults":30}'
```

Fetch metadata for each result the same way as Step 3.

## Step 5: Judge significance

For each email (inbox + spam), decide: NOTIFY or skip.

RAISE significance (lean toward NOTIFY) if:
- Sender is someone Rodolfo has emailed before or is in an active thread
- Subject contains: deadline, frist, termin, invoice, rechnung, appointment, confirmation, bestätigung
- Sender domain is healthcare (arzt, praxis, klinik), legal, financial, or German government (finanzamt, kranken, jobcenter, einwohnermeldeamt, agentur-fuer-arbeit, bundesamt, behörde)
- Looks like a recruiter or job opportunity — especially relevant (active job search): LinkedIn, Xing, direct headhunter outreach
- Email is a direct question or personal request
- Email is in SPAM but looks legitimate based on domain, professional tone, or personal relevance

LOWER significance (skip silently) if:
- Sender or domain is in the Blocked Senders or Blocked Domains sections of email-prefs.md
- Newsletter, unsubscribe link present, marketing, promotional
- GitHub CI, Dependabot, Actions notifications with no @mention or PR review request
- Automated system notification with no required human action

## Step 6: Atomic write to pulse-log.md

Compute the current timestamp in Europe/Berlin timezone:

```bash
python3 -c "from datetime import datetime; import zoneinfo; tz=zoneinfo.ZoneInfo('Europe/Berlin'); print(datetime.now(tz).isoformat(timespec='seconds'))"
```

Read the current pulse-log.md again (to get the full existing log content).

Rewrite ~/.open-assistant/memory/pulse-log.md entirely with the Write tool — a single write:

```
# Pulse Log

last_successful_run: <NEW_TIMESTAMP>

## Log

[<NEW_TIMESTAMP>] INBOX (since <PREVIOUS_TIMESTAMP>): <N> emails checked
  - NOTIFIED: "<Subject> — <one-line summary>" (repeat for each notable item)
  - [SPAM] NOTIFIED: "<Subject> — <one-line summary>" (repeat for spam rescues)
  - skipped: <N> (<brief reason e.g. newsletters, GitHub>)

<EXISTING LOG ENTRIES HERE — copy verbatim, do not modify>
```

If email-prefs.md did not exist before this run, create it now:

```
# Email Preferences

## Blocked Senders

## Blocked Domains

## Trusted Senders / Spam Rescue

## Pattern Notes
```

## Step 7: Return result

If ≥1 email was notable:

Return a plain-text numbered list — no intro, no sign-off, numbers only:

```
1. <Sender name/role> — <one-line description of what needs attention>
2. [SPAM] <Sender> — <one-line description>
```

If nothing was notable: return an empty string. Do not output anything else.
```

- [ ] **Step 2: Verify the skill file loads without errors**

```bash
cat /Users/beam/open-assitant/.claude/skills/pulse/SKILL.md
```

Expected: file prints cleanly with no truncation.

- [ ] **Step 3: Commit**

```bash
cd /Users/beam/open-assitant
git add .claude/skills/pulse/SKILL.md
git commit -m "feat: add pulse skill for hourly background email surveillance"
```

---

### Task 4: Inbox skill

**Files:**
- Create: `.claude/skills/inbox/SKILL.md`

- [ ] **Step 1: Create the skill file**

Create `.claude/skills/inbox/SKILL.md` with this exact content:

```markdown
# Inbox Skill

You are running the inbox manager — weekly review and cleanup.

CONSTRAINTS:
- DO NOT write to any memory file other than pulse-log.md and email-prefs.md.
- DO NOT execute any action (archive, block, delete) without explicit user confirmation.
- NEVER delete emails unless the user explicitly types "delete N". Numbers or "all" alone cannot trigger deletion.
- Do NOT greet the user. Do NOT add filler text.

## Step 1: Read context

Read ~/.open-assistant/memory/pulse-log.md with the Read tool.
Read ~/.open-assistant/memory/email-prefs.md with the Read tool.

Review the full pulse log for the week: patterns of skipped senders, repeated rescues from spam, high-volume senders.

## Step 2: Scan current inbox for bulk patterns

```bash
gws gmail users messages list --params '{"q":"in:inbox","maxResults":100}' --page-all --page-limit 3
```

For message IDs, fetch sender/subject metadata in batches. Identify:
- Senders with ≥5 emails that were consistently skipped by pulse (all low signal)
- Unread threads older than 14 days with no notable signal
- Domains generating ≥10 emails with no notable signal across all runs
- Senders in spam that pulse has rescued multiple times → trusted list candidate

## Step 3: Produce triage report

Output a plain-text report (NO markdown asterisks, NO bold, NO headers with #).
Use ALL-CAPS labels for section separation. This ensures readability in both
the Telegram scheduled delivery path (plain text) and the interactive /inbox path.

Format:
```
Inbox review — week of <DATE>:

TO CONFIRM (reply with numbers, e.g. "1,3" or "all"):
1. <Specific action> — <brief reason>
2. <Specific action> — <brief reason>
...

REQUIRES EXPLICIT "delete N" (e.g. "delete 5"):
<N>. Delete <count> emails from <sender/domain> — <brief reason>
```

Do not include delete items in the TO CONFIRM section. Do not present delete items if there are none.

Wait for the user's reply before taking any action.

## Step 4: Execute confirmed actions

Parse the user's reply:

For numbers or "all" (confirmable actions only):
- Archive threads:
  ```bash
  gws gmail users messages batchModify --params '{"userId":"me"}' --json '{"ids":["<id1>","<id2>",...],"removeLabelIds":["INBOX"]}'
  ```
- Block sender: add entry to Blocked Senders section of email-prefs.md with today's date
- Block domain: add entry to Blocked Domains section of email-prefs.md with today's date
- Trust sender/domain: add entry to Trusted Senders section of email-prefs.md with today's date and reason

For "delete N" only (exact phrase with item number):
  ```bash
  gws gmail users messages batchDelete --params '{"userId":"me"}' --json '{"ids":["<id1>","<id2>",...]}'
  ```
- Confirm count before executing: "This will permanently delete <N> emails from <sender>. Confirm?"

For anything else: ask for clarification.

After each action, briefly confirm: "Done — <what was done>."

## Step 5: Update pulse-log.md

After all actions are complete, compute the current timestamp:

```bash
python3 -c "from datetime import datetime; import zoneinfo; tz=zoneinfo.ZoneInfo('Europe/Berlin'); print(datetime.now(tz).isoformat(timespec='seconds'))"
```

Read the current pulse-log.md. Rewrite it entirely with a CLEANUP entry inserted at the top of the ## Log section:

```
[<TIMESTAMP>] CLEANUP: <summary of all actions taken> (inbox manager)
```

Use the same atomic Write approach as the pulse skill. Preserve all existing log entries.

Output a brief summary of all actions taken (3-5 lines max).
```

- [ ] **Step 2: Verify the skill file loads without errors**

```bash
cat /Users/beam/open-assitant/.claude/skills/inbox/SKILL.md
```

Expected: file prints cleanly.

- [ ] **Step 3: Commit**

```bash
cd /Users/beam/open-assitant
git add .claude/skills/inbox/SKILL.md
git commit -m "feat: add inbox manager skill for weekly email triage and cleanup"
```

---

### Task 5: Wire schedules.yaml

**Files:**
- Modify: `~/.open-assistant/schedules.yaml` (user config, not in repo)

> Note: `schedules.yaml` is the live config at `~/.open-assistant/schedules.yaml`. It is not version-controlled. The scheduler loads it on startup via `SCHEDULES_PATH = pathlib.Path.home() / ".open-assistant" / "schedules.yaml"`.

- [ ] **Step 1: Add pulse and inbox-manager entries to schedules.yaml**

Open `~/.open-assistant/schedules.yaml`. Under the `tasks:` key, add these two entries (replace `YOUR_CHAT_ID` with Rodolfo's actual Telegram chat ID, obtainable by running `/chatid` in the bot):

```yaml
  - name: pulse
    cron: "0 8-18 * * 1-5"    # every hour on the hour, 8am–6pm, weekdays
    prompt: "DO NOT write to memory files other than pulse-log.md. Run the /pulse skill."
    notify:
      telegram: ["YOUR_CHAT_ID"]

  - name: inbox-manager
    cron: "0 8 * * 1"    # Mondays at 8am
    prompt: "DO NOT write to memory files other than pulse-log.md and email-prefs.md. Run the /inbox skill."
    notify:
      telegram: ["YOUR_CHAT_ID"]
```

- [ ] **Step 2: Validate YAML parses correctly**

```bash
python3 -c "
import yaml, pathlib
path = pathlib.Path.home() / '.open-assistant' / 'schedules.yaml'
data = yaml.safe_load(path.read_text())
tasks = data.get('tasks', [])
names = [t['name'] for t in tasks]
print('Tasks found:', names)
assert 'pulse' in names, 'pulse task missing'
assert 'inbox-manager' in names, 'inbox-manager task missing'
print('OK')
"
```

Expected output:
```
Tasks found: [..., 'pulse', 'inbox-manager']
OK
```

- [ ] **Step 3: Verify APScheduler accepts the cron expressions**

```bash
python3 -c "
from apscheduler.triggers.cron import CronTrigger
t1 = CronTrigger.from_crontab('0 8-18 * * 1-5')
t2 = CronTrigger.from_crontab('0 8 * * 1')
print('pulse trigger:', t1)
print('inbox-manager trigger:', t2)
print('OK')
"
```

Expected: both triggers print without error.

- [ ] **Step 4: Run full test suite one final time**

```bash
cd /Users/beam/open-assitant && python -m pytest -v
```

Expected: all pass.

- [ ] **Step 5: Final commit**

```bash
cd /Users/beam/open-assitant
git add src/ tests/ .claude/skills/
git commit -m "feat: complete pulse and inbox manager — skills, commands, scheduler guard"
```

---

## Manual Smoke Test (after deployment)

Once the bot is running:

1. **Verify `/inbox` command works:** Send `/inbox` in Telegram. Expected: inbox manager produces a triage report.

2. **Verify pulse runs silently when nothing notable:** Wait for a pulse run (8-18h weekday). If inbox is quiet, no Telegram message should arrive.

3. **Verify pulse notifies when something is notable:** Send yourself a test email with "Urgent: action required" subject. Within the hour, expect a numbered Telegram message.

4. **Verify spam rescue:** Move a real email to spam and wait for the next pulse. Expected: it surfaces with `[SPAM]` prefix if it looks legitimate.

5. **Verify gap recovery:** Stop the assistant process for 2 hours. Restart. The next pulse should query from the last `last_successful_run` timestamp, not 1h ago. Check `pulse-log.md` header to confirm.
