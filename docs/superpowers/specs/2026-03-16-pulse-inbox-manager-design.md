# Pulse & Inbox Manager Design Spec
**Date:** 2026-03-16
**Status:** Approved

---

## Context

Open Assistant already has a YAML-driven scheduler (`schedules.yaml`) that dispatches Claude agent tasks via `ask_agent`. The established pattern for all scheduled intelligence is: **YAML cron + existing scheduler + `.claude/skills/<name>/SKILL.md`**. No dedicated Python modules are created for scheduled behavior — the skill IS the task.

The user (Rodolfo) needs:
1. Hourly background email surveillance that catches important messages (including spam rescues) without interrupting him unless something clears a significance threshold
2. A weekly inbox management tool that reviews accumulated intelligence and helps him clean up — with all destructive actions user-confirmed only

---

## Component 1 — `/pulse` Skill (Hourly Background Surveillance)

### Schedule

```yaml
- name: pulse
  cron: "0 8-18 * * 1-5"    # every hour on the hour, 8am–6pm, weekdays
  prompt: "DO NOT write to memory files other than pulse-log.md. Run the /pulse skill."
  notify:
    telegram: ["YOUR_CHAT_ID"]
```

### Behavior

The pulse is a silent background intelligence job. It always runs; it only notifies when something clears the significance threshold.

**On each run:**

1. Read `~/.open-assistant/memory/pulse-log.md` — extract `last_successful_run` timestamp from the top of the file (ISO 8601 with timezone). If the file does not exist or has no timestamp, default to 1 hour ago.
2. Read `~/.open-assistant/memory/email-prefs.md` — load blocked senders, blocked domains, trusted senders, and accumulated pattern notes.
3. Query inbox for emails since `last_successful_run`:
   ```
   gws gmail users messages list --params '{"q":"in:inbox after:<UNIX_EPOCH>","maxResults":50}'
   ```
4. Query SPAM for emails in last 24h (fixed window — spam is re-checked each run to catch items that arrive and age):
   ```
   gws gmail users messages list --params '{"q":"in:spam newer_than:1d","maxResults":30}'
   ```
5. For each email, Claude judges significance using full context: sender relationship, subject, thread history, urgency signals, time-sensitivity, and `email-prefs.md` patterns. Blocked senders/domains are skipped silently.
6. Update `last_successful_run` timestamp at the top of `pulse-log.md` **only after all checks succeed**. A failed/interrupted run leaves the previous timestamp intact so the next run covers the gap.
7. Append a log entry to `pulse-log.md` (see format below).
8. If ≥1 item is notable: send a single Telegram message with all notable items as a numbered list.

### Significance Threshold

Claude judges significance holistically — no fixed rules. Signals that raise significance:
- Sender is in an active thread or known contact
- Time-sensitive content (deadlines, appointments, confirmations)
- Healthcare, legal, financial, or official German government senders
- Recruiter or job opportunity (especially relevant given active job search)
- Direct questions or requests requiring a response
- Anything in SPAM that looks legitimate based on sender domain, content, or relationship

Signals that lower significance (skip silently):
- Newsletters, marketing, automated notifications
- GitHub/CI notifications with no action required
- Senders or domains in `email-prefs.md` blocked list
- Low-signal bulk mail

### Notification Format

Single Telegram message, numbered list, one line per item, compact:

```
1. Dr. Müller replied — needs more info on your bloodwork
2. [SPAM] Zalando recruiter — Senior Data Engineer role
3. Finanzamt confirmation — tax submission accepted
```

User can reply referencing numbers only: "1 — tell him I'll send it tomorrow" or "2 ignore".

### Spam Rescue

When the pulse surfaces a SPAM email as notable, the notification line is prefixed with `[SPAM]`. If the user acts on it (via the agent conversation), Claude updates `email-prefs.md` to add the sender to trusted senders. Pattern notes are accumulated over time (e.g., "LinkedIn recruiter emails often land in spam").

---

## Component 2 — `/inbox` Skill (Weekly Inbox Manager)

### Schedule

```yaml
- name: inbox-manager
  cron: "0 8 * * 1"    # Mondays at 8am
  prompt: "DO NOT write to memory files other than pulse-log.md and email-prefs.md. Run the /inbox skill."
  notify:
    telegram: ["YOUR_CHAT_ID"]
```

Also triggerable on-demand via `/inbox` Telegram command (registered in `src/channels/telegram.py`).

### Behavior

1. Read `~/.open-assistant/memory/pulse-log.md` — review the full week's accumulated log for patterns.
2. Read `~/.open-assistant/memory/email-prefs.md` — current blocked/trusted state.
3. Scan current inbox for bulk patterns (many emails from same sender/domain, old unread threads, etc.).
4. Produce a triage report with numbered suggestions:

```
Inbox review — week of Mar 16:

Suggested actions:
1. Block newsletter@foo.com — 14 emails this week, all skipped by pulse
2. Archive 8 threads from noreply@github.com older than 30 days
3. Block domain @promotions.shopify.com — 22 emails, no signal
4. 3 unread threads >2 weeks old — review and archive?

Spam patterns noticed:
5. LinkedIn recruiter emails consistently landing in spam — add linkedin.com to trusted?

Reply with numbers to confirm (e.g. "1,3,5") or "all".
```

5. User replies confirming actions. Claude executes each via `gws gmail` commands:
   - Block sender: update `email-prefs.md`, optionally filter future mail
   - Block domain: update `email-prefs.md`
   - Bulk archive: `gws gmail users messages batchModify` with `ARCHIVE` action
   - Bulk delete: `gws gmail users messages batchDelete` (user must explicitly say "delete", not just confirm)
   - Trust sender/domain: update `email-prefs.md` trusted list

6. After executing actions, append a cleanup entry to `pulse-log.md`:
   ```
   [2026-03-16T08:30] CLEANUP: blocked newsletter@foo.com, blocked @promotions.shopify.com,
     archived 8 GitHub threads. Trusted linkedin.com for spam rescue.
   ```

This ensures the next pulse run starts with accurate state and does not re-surface handled items.

### User-Controlled Actions Only

The inbox manager **never** deletes, blocks, or archives without explicit user confirmation per action. It lists suggestions and waits. Bulk delete specifically requires the word "delete" from the user — "confirm" or a number alone is not enough for destructive operations.

---

## Memory Files

### `~/.open-assistant/memory/pulse-log.md`

Dual-purpose: state tracking (top) + history log (body).

```markdown
# Pulse Log

last_successful_run: 2026-03-16T10:00:00+01:00

## Log

[2026-03-16T10:00] INBOX (since 2026-03-16T09:00): 8 emails checked
  - NOTIFIED: "Dr. Müller re: follow-up" — needs reply
  - NOTIFIED: [SPAM rescued] "Recruiter - Senior DE role at Zalando"
  - skipped: 6 (newsletters, GitHub notifications)

[2026-03-16T09:00] INBOX (since 2026-03-16T08:00): 3 emails checked
  - skipped: 3 (low signal)

[2026-03-16T08:05] CLEANUP: blocked newsletter@foo.com, archived 12 threads (inbox manager)
```

Written by: pulse skill (every run), inbox manager (after cleanup actions).
Read by: pulse skill (for `last_successful_run`), inbox manager (for weekly triage).

### `~/.open-assistant/memory/email-prefs.md`

Claude's accumulated email intelligence.

```markdown
# Email Preferences

## Blocked Senders
- newsletter@foo.com (blocked 2026-03-16 via inbox manager)

## Blocked Domains
- @promotions.shopify.com (blocked 2026-03-16 via inbox manager)

## Trusted Senders / Spam Rescue
- *@linkedin.com — recruiter emails often land in spam, always surface (added 2026-03-16)

## Pattern Notes
- GitHub notifications: only surface if @mentions or PR review requests, ignore CI/dependabot
- Finanzamt emails: always surface regardless of folder
```

Written by: inbox manager (blocks, trusts), pulse skill (pattern notes over time).
Read by: pulse skill (every run to inform judgment).

---

## Scheduler Wiring

No changes to `scheduler.py` or `main.py` — the existing infrastructure handles everything.

Two new entries in `schedules.yaml`:
- `pulse`: `0 8-18 * * 1-5`
- `inbox-manager`: `0 8 * * 1`

One new Telegram command in `src/channels/telegram.py`:
- `/inbox` → calls `ask_agent("/inbox", chat_id)`

Two new skills:
- `.claude/skills/pulse/SKILL.md`
- `.claude/skills/inbox/SKILL.md`

---

## Success Criteria

| Criterion | Observable signal |
|-----------|-----------------|
| No inbox gap on connection loss | Next pulse run covers from `last_successful_run`, not from 1h ago |
| Spam rescue works | Notable spam emails surface in Telegram with `[SPAM]` prefix |
| Silent when nothing notable | Pulse runs without Telegram message when only newsletters/noise |
| Inbox manager is non-destructive | No email is deleted or blocked without explicit user confirmation |
| Pulse log stays current | After inbox manager cleanup, next pulse does not re-surface handled items |
| User can reference by number | Telegram notification uses numbered list; user replies with numbers only |
