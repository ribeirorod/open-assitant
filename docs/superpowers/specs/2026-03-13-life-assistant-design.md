# Life Assistant Design Spec
**Date:** 2026-03-13
**Status:** Approved

---

## Context

Rodolfo is a 40-year-old data engineer living in Germany. He is simultaneously:
- Expecting his first child (wife 9 months pregnant — baby imminent)
- Launching an app
- Searching for a new job

He struggles with hyper-focus (dives into one area and neglects others), procrastination on uncomfortable tasks, and managing the structural demands of life in Germany (bureaucracy, tax deadlines, registrations). He wants to apply a project management mindset across all life areas: relationship, fitness/health, work, leisure,professional projects, family & friends, and life in Germany (bureaucracy, tax deadlines, registrations).

The assistant runs on Telegram (voice + text), has access to Gmail, Google Calendar, Google Tasks, Google Drive, and Google Docs via the `gws` CLI, and uses the Claude Agent SDK for multi-turn sessions.

---

## Goals

1. Maintain a persistent personal knowledge base the agent reads to give contextually accurate, personalized help
2. Proactively surface priorities, missed emails, and avoided tasks via scheduled Telegram messages
3. Help structure realistic daily and weekly plans — no overcommitting
4. Surface and name things being procrastinated
5. Allow general-purpose capture via `/note`
6. Act on the user's behalf (send emails, create events, update tasks) with explicit confirmation

---

## Component 1 — Personal Memory System

### Structure

```
~/.open-assistant/memory/
  index.md            ← one-liner per topic + filename pointer
  projects.md         ← current projects, status, priority, next actions
  commitments.md      ← baby due date, app launch target, job search status, key relationships, recurring commitments
  preferences.md      ← focus hours, gym schedule, communication tone, piano practice goal, work style
  procrastination.md  ← known avoidance patterns + items being avoided and for how long
  german-life.md      ← bureaucracy deadlines: tax filing, Krankenkasse renewals, Anmeldung tasks, baby registration (Geburtsurkunde, Kindergeld, etc.)
```

New topic files are created on demand. When the agent identifies a topic that doesn't fit an existing file, it creates a new file and adds a one-line entry to `index.md`.

### `index.md` format

```markdown
- projects: current projects, status and next actions → projects.md
- commitments: key life commitments and deadlines → commitments.md
- preferences: personal style, focus hours, habits → preferences.md
- procrastination: known avoidance patterns and items → procrastination.md
- german-life: bureaucracy, tax and registration deadlines → german-life.md
```

### Memory access mechanism

The agent has `Read` and `Write` in its `allowed_tools`. Memory access is pure file I/O — no new tooling required. The memory directory is created during the bootstrap session if it doesn't exist (`mkdir -p ~/.open-assistant/memory/`).

The system prompt addendum (to be added to `SYSTEM_PROMPT` in `src/agent/core.py`) reads:

```
MEMORY — your persistent knowledge base lives at ~/.open-assistant/memory/:
- Always start every response by reading index.md with the Read tool.
- Then read whichever topic files are relevant to the current request.
- When you learn something new (project update, deadline, preference, avoidance pattern),
  update the relevant memory file immediately using the Write tool.
- If a topic has no existing file, create one and add a one-line entry to index.md.
- Format for procrastination.md entries: "- [YYYY-MM-DD added] Item description"
  so age can be calculated.
```

### How the agent uses memory

At the start of every conversation and every scheduled task, the agent reads `index.md` first. It then pulls only the files relevant to the current task:

| Task | Files read |
|------|-----------|
| `/plan` | `projects.md`, `commitments.md`, `preferences.md`, `procrastination.md` |
| `/week` | all files |
| `/avoid` | `procrastination.md`, `projects.md` |
| `/update` | whichever file matches the topic |
| Morning briefing | `projects.md`, `commitments.md`, `preferences.md`, `procrastination.md` |
| Bureaucracy check | `german-life.md`, `commitments.md` |

### How memory stays current

The agent updates memory proactively during any conversation when it learns something new (project status change, new deadline, expressed preference). `/update [project/topic]` makes this explicit. The system prompt instructs the agent to treat memory as a living document and to always write changes back.

### Bootstrap session

Before the scheduler is useful, one dedicated onboarding conversation fills the initial memory files. The agent asks structured questions: current projects and their status, key deadlines, German bureaucracy items, focus hours, gym schedule, communication preferences. Takes 10–15 minutes via voice or text.

### Future: Archiving

When projects are completed or commitments expire, they will be moved to an `archive/` subfolder rather than deleted. Threshold and trigger for archiving TBD in a future design session.

---

## Component 2 — Telegram Commands (Skills)

### Handler registration (`src/channels/telegram.py`)

Each new command is registered in `build_telegram_app()` using `CommandHandler`. The handler extracts any arguments from `update.message.text` (everything after the command word) and passes a structured prompt to `ask_agent`. Pattern:

```python
async def _plan(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_allowed(update): return
    chat_id = str(update.effective_chat.id)
    stop = asyncio.Event()
    typing_task = asyncio.create_task(_keep_typing(update, stop))
    try:
        response = await ask_agent("/plan", chat_id)
    finally:
        stop.set(); typing_task.cancel()
    await _send_markdown(update, response)

# In build_telegram_app():
app.add_handler(CommandHandler("plan", _plan))
app.add_handler(CommandHandler("week", _week))
app.add_handler(CommandHandler("note", _note))
app.add_handler(CommandHandler("avoid", _avoid))
app.add_handler(CommandHandler("update", _update))
```

For `/note`, the text argument is passed directly: `await ask_agent(f"/note {args}", chat_id)`. Voice messages continue to use the existing `_handle_voice` handler, which transcribes and forwards to the agent as plain text — the agent's system prompt and conversation context determine how to treat it. No separate voice routing logic for `/note` is required.

### `/plan`
**Trigger:** User sends `/plan`
**Workflow:**
1. Read memory (projects, commitments, preferences, procrastination)
2. Read today's calendar events
3. Read unread/flagged emails — surface anything missed or requiring action
4. Read open Google Tasks
5. Synthesize: propose exactly 3 realistic priorities for the day
6. Suggest any calendar events or tasks that should be created based on email content
7. Flag any item from the procrastination file that has been sitting >3 days
8. Ask "Does this look right?" — adjust if needed

**Output format:** Structured markdown. Max 10 lines. Bold the 3 priorities.

---

### `/week`
**Trigger:** User sends `/week`
**Workflow:**
1. Read all memory files
2. Read next 7 days of calendar
3. Read open tasks
4. Identify: overloaded days, missing time for gym/family/piano, conflicts
5. Suggest time blocks for protected activities
6. Ask if user wants to create those blocks

---

### `/note [text]`
**Trigger:** User sends `/note` followed by text. For voice: user sends a voice message at any time and the agent treats it as a note if no other context is active (existing voice handler already transcribes all voice messages and forwards them to the agent).
**Purpose:** General-purpose capture. Can be a task ("remember to call the Finanzamt"), a goal ("I need more time for piano practice"), an idea, a reminder — anything. Agent determines the right place to store it (Google Tasks, memory file, or both) and confirms what it did.
**No state tracking required:** `/note` is a one-shot command followed immediately by the note text in the same message. No multi-update state machine needed.

---

### `/avoid`
**Trigger:** User sends `/avoid`
**Workflow:**
1. Read `procrastination.md` and open tasks older than 3 days
2. List avoided items by name, with how long they've been sitting (calculated from `[YYYY-MM-DD added]` timestamp in `procrastination.md`)
3. Ask: "Which one can you do 30 minutes on today?"
4. User replies with the item; agent computes the current time in Europe/Berlin via Python Bash one-liner, then runs `gws calendar events list --params '{"calendarId":"primary","timeMin":"<NOW>","timeMax":"<END_OF_DAY>","singleEvents":true,"orderBy":"startTime"}'` to get remaining events as structured JSON. Agent identifies the first gap of ≥30 minutes and proposes it (e.g., "14:00–14:30 looks free — want me to block it?"). If no gap exists or parsing fails, agent asks: "What time works for you?"
5. Creates event only after explicit confirmation — never auto-creates
6. Event title format: `Focus: [item name]`

---

### `/update [project or topic]`
**Trigger:** User sends `/update` optionally followed by a project or topic name
**Workflow:**
1. Ask what's changed
2. Update the relevant memory file
3. Confirm what was written

---

## Component 3 — Scheduled Jobs (`schedules.yaml`)

Jobs use the existing YAML format. Replace `YOUR_CHAT_ID` with João's Telegram chat ID (obtained by messaging the bot and checking logs).

```yaml
tasks:
  - name: morning-briefing
    cron: "0 8 * * 1-5"
    prompt: "..."   # see per-job prompt guidance below
    notify:
      telegram: ["YOUR_CHAT_ID"]

  - name: evening-review
    cron: "30 19 * * *"
    prompt: "..."
    notify:
      telegram: ["YOUR_CHAT_ID"]

  - name: weekly-planning
    cron: "0 17 * * 0"
    prompt: "..."
    notify:
      telegram: ["YOUR_CHAT_ID"]

  - name: midweek-pulse
    cron: "0 12 * * 3"
    prompt: "..."
    notify:
      telegram: ["YOUR_CHAT_ID"]

  - name: bureaucracy-check
    cron: "0 9 1 * *"
    prompt: "..."
    notify:
      telegram: ["YOUR_CHAT_ID"]
```



**Note on session isolation and scheduler wiring:** The existing `scheduler.py` calls `ask_agent(task["prompt"], chat_id=f"sched:{name}")`. Each job's `prompt` field in `schedules.yaml` is the literal string passed to the agent. The `chat_id` is derived from the task name — this is existing behavior requiring no changes. The prompt strings in the jobs below must replace the `"..."` placeholders in `schedules.yaml`.

**Note on memory concurrency:** The agent uses the `Write` tool which overwrites entire files. Two risks exist:
1. *Scheduled job races:* Mitigated by designing scheduled jobs as read-only — they must not write to memory files. Enforced via system prompt instruction in each job prompt.
2. *Rapid interactive messages:* `python-telegram-bot` processes updates sequentially via its internal update queue per chat — concurrent agent turns for the same chat_id are not possible in the existing architecture. This risk is accepted as negligible for a single-user assistant. This is intentional — briefings are one-way pushes. Any follow-up the user sends after a briefing goes into their own interactive session naturally, with full conversation context. No special session bridging is needed.

### `morning-briefing` — 8:00 AM, Monday–Friday

```
Read ~/.open-assistant/memory/index.md, then read projects.md, commitments.md, preferences.md, and procrastination.md.
Then run: gws calendar +agenda to get today's events.
Then run: gws gmail +triage to surface unread emails from the last 18 hours needing attention.
Then run: gws tasks tasks list --params '{"tasklist":"@default"}' to get open tasks.

Output a structured morning briefing:
**Today's 3 priorities** (realistic given the calendar — no more than 3)
**Emails needing action** (max 3, one line each with suggested next step)
**One item to face today** (the oldest item in procrastination.md by added date)

Tone: direct, no filler, no emoji. Max 15 lines total.
```

### `evening-review` — 7:30 PM, daily

```
Read ~/.open-assistant/memory/projects.md.
Use Bash to compute today's start-of-day in Europe/Berlin timezone: `python3 -c "from datetime import datetime; import zoneinfo; tz=zoneinfo.ZoneInfo('Europe/Berlin'); print(datetime.now(tz).replace(hour=0,minute=0,second=0,microsecond=0).isoformat())"`. Then run: gws tasks tasks list --params '{"tasklist":"@default","showCompleted":true,"completedMin":"<RESULT>"}' to see what was completed today.
Run: gws calendar +agenda to see what actually happened today.

Output in 5 lines max:
- What got done (completed tasks and attended events)
- What carries forward to tomorrow
- One honest reflection question (no filler, something specific to today)
```

### `weekly-planning` — Sunday, 5:00 PM

```
Read all files in ~/.open-assistant/memory/.
Use Bash with this portable Python one-liner to get next Monday and Sunday in Europe/Berlin time:
`python3 -c "from datetime import datetime, timedelta; import zoneinfo; tz=zoneinfo.ZoneInfo('Europe/Berlin'); now=datetime.now(tz); offset=now.strftime('%z'); offset=offset[:3]+':'+offset[3:]; today=now.date(); monday=today+timedelta(days=(7-today.weekday())%7 or 7); sunday=monday+timedelta(days=6); print(monday.isoformat()+'T00:00:00'+offset, sunday.isoformat()+'T23:59:59'+offset)"`
Then run: gws calendar events list --params '{"calendarId":"primary","timeMin":"<MONDAY>","timeMax":"<SUNDAY>"}' for the week ahead.
Run: gws tasks tasks list --params '{"tasklist":"@default"}' for open tasks.

Produce a weekly overview:
- Days that look overloaded (flag if >3 commitments)
- Missing protected time (gym needs 3 slots, family/relationship time, piano practice)
- Suggested time blocks to protect (list only — do NOT create calendar events)
- One thing to defer if the week is too full

End with: "Reply to this message or send /week to finalize and create these blocks."
```

### `midweek-pulse` — Wednesday, 12:00 PM

```
Read ~/.open-assistant/memory/projects.md.
Run: gws tasks tasks list --params '{"tasklist":"@default","showCompleted":true}' — use completed field to infer this week's progress.
If gws does not return completed tasks with dates, fall back to reading projects.md for current status only.

Output in 3–4 lines:
- Status on the main 3 projects (on track / slipping / blocked)
- One concrete thing to do before Friday if anything is off-track
```

### `bureaucracy-check` — 1st of every month, 9:00 AM

```
Read ~/.open-assistant/memory/german-life.md and commitments.md.

Surface any deadline, renewal, or required action due in the next 30 days.
If baby has arrived (check commitments.md for birth date), include German post-birth requirements:
Geburtsurkunde (7 days), Krankenkasse registration (immediate), Kindergeld application (within 6 months), Elternzeit notification.

Format as a checklist. Include the exact due date for each item.
```

---

## System Prompt Updates

The agent system prompt must be extended with:

1. **Memory instructions:** At the start of every session, read `~/.open-assistant/memory/index.md`. Pull relevant topic files before responding. Update memory files when new information is learned.
2. **Planning discipline:** When helping with daily or weekly plans, never suggest more than 3 meaningful tasks per day. Flag if the user is overloading themselves.
3. **Procrastination protocol:** If a task or project appears repeatedly across conversations without progress, name it directly and ask what's blocking it.
4. **Confirmation before action:** Always confirm before sending emails, creating calendar events, or modifying tasks. One short sentence is enough.
5. **Communication tone:** Direct, structured, no emoji, no filler. Match the user's register.

---

## Backlog (Future Sprints)

- **Email management skill:** Triage inbox, draft replies, archive, label — full email workflow command
- **Archive system:** Move completed projects and expired commitments to `memory/archive/` once a threshold is reached
- **Semantic memory search:** Replace index.md file-pull with embedding-based retrieval when memory grows large

---

## Success Criteria

| Criterion | Observable signal |
|-----------|------------------|
| Agent knows João's context | Briefings reference current projects by name without prompting |
| Morning briefing is actionable | Contains ≤3 priorities and at least one email action item when unread mail exists; sent by 8:05 AM on weekdays |
| Nothing falls through the cracks | German deadlines and commitments appear in bureaucracy-check ≥7 days before due |
| Procrastination surfacing | `/avoid` returns items with `[YYYY-MM-DD added]` timestamps; items in `procrastination.md` older than 3 days are named directly in every morning briefing |
| Realistic daily plans | `/plan` never proposes more than 3 meaningful tasks |
| Voice capture works | Voice message → `/note` → Google Tasks entry confirmed within one agent turn |
