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
tasks:
  - name: pulse
    cron: "0 8-18 * * 1-5"    # every hour on the hour, 8am–6pm, weekdays
    prompt: "DO NOT write to memory files other than pulse-log.md. Run the /pulse skill."
    notify:
      telegram: ["YOUR_CHAT_ID"]
```

### Behavior

The pulse is a silent background intelligence job. It always runs; it only notifies when something clears the significance threshold. **When nothing is notable, the pulse skill returns an empty string.** The scheduler (via `_run_task`) must guard against forwarding empty responses — a one-line check is added: `if response.strip(): <send notifications>`.

**On each run:**

1. Read `~/.open-assistant/memory/pulse-log.md` — extract `last_successful_run` timestamp from the top of the file using this fallback chain:
   - Valid, parseable ISO 8601 timestamp → use as `timeMin`
   - Absent, malformed, or unparseable → default to 1 hour ago
   - Timestamp in the future (clock skew, DST edge) → default to 1 hour ago
   - Timestamp older than 24 hours (long outage) → cap to 24 hours ago; note that inbox and spam windows will be aligned but a longer gap is not covered by the spam query (acceptable — inbox query covers it)
   - File does not exist → default to 1 hour ago; create the file with canonical structure at the end of a successful run

2. Read `~/.open-assistant/memory/email-prefs.md` — load blocked senders, blocked domains, trusted senders, and accumulated pattern notes. If the file does not exist, proceed with empty lists and create it with canonical structure at the end of the first successful run.

3. Query inbox for emails since `last_successful_run`:
   ```
   gws gmail users messages list --params '{"q":"in:inbox after:<UNIX_EPOCH>","maxResults":50}'
   ```

4. Query SPAM for emails in the last 24h (fixed window — spam is re-checked each run to catch items that arrive and age):
   ```
   gws gmail users messages list --params '{"q":"in:spam newer_than:1d","maxResults":30}'
   ```

5. For each email, Claude judges significance using full context: sender relationship, subject, thread history, urgency signals, time-sensitivity, and `email-prefs.md` patterns. Blocked senders/domains are skipped silently. See Significance Threshold below.

6. **Atomic write to `pulse-log.md`:** In a single `Write` operation, rewrite the entire file with:
   - Updated `last_successful_run` header (new timestamp for this run)
   - Appended log entry for this run
   This ensures the timestamp and the log entry are always consistent. The write happens only after both Gmail queries have completed — a failed/interrupted query leaves the previous file intact so the next run covers the gap.

7. If ≥1 item is notable: return a numbered Telegram message. Otherwise: return an empty string (no notification sent).

### Significance Threshold

Claude judges significance holistically — no fixed rules. Signals that raise significance:
- Sender is in an active thread or known contact
- Time-sensitive content (deadlines, appointments, confirmations)
- Healthcare, legal, financial, or official German government senders
- Recruiter or job opportunity (especially relevant given active job search)
- Direct questions or requests requiring a response
- Anything in SPAM that looks legitimate based on sender domain, content, or relationship context

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

When the pulse surfaces a SPAM email as notable, the notification line is prefixed with `[SPAM]`. If the user acts on it via the agent conversation, Claude updates `email-prefs.md` to add the sender to trusted senders and appends a pattern note. Pattern notes accumulate over time (e.g., "LinkedIn recruiter emails often land in spam").

---

## Component 2 — `/inbox` Skill (Weekly Inbox Manager)

### Schedule

```yaml
tasks:
  - name: inbox-manager
    cron: "0 8 * * 1"    # Mondays at 8am
    prompt: "DO NOT write to memory files other than pulse-log.md and email-prefs.md. Run the /inbox skill."
    notify:
      telegram: ["YOUR_CHAT_ID"]

  - name: pulse
    cron: "0 8-18 * * 1-5"    # every hour on the hour, 8am–6pm, weekdays
    prompt: "DO NOT write to memory files other than pulse-log.md. Run the /pulse skill."
    notify:
      telegram: ["YOUR_CHAT_ID"]
```

Also triggerable on-demand via `/inbox` Telegram command (no arguments — `/inbox` alone; any trailing text is ignored). The handler follows the established pattern:

```python
# In telegram.py:
async def _inbox(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await _dispatch(update, _skill("inbox"))

# In build_telegram_app():
app.add_handler(CommandHandler("inbox", _inbox))
```

### Behavior

1. Read `~/.open-assistant/memory/pulse-log.md` — review the full week's accumulated log for patterns.
2. Read `~/.open-assistant/memory/email-prefs.md` — current blocked/trusted state.
3. Scan current inbox for bulk patterns (many emails from same sender/domain, old unread threads, etc.).
4. Produce a triage report with numbered suggestions, separated into two groups. The report uses **plain text formatting only** — no markdown bold or headers — because when delivered via the scheduler path (Monday 8am), the message goes through `telegram_notify.py` which sends plain text without MarkdownV2 conversion. The on-demand `/inbox` path goes through `_dispatch` → `_send_markdown` which applies `markdownify`, but formatting must be safe for both delivery paths. Use ALL-CAPS section labels instead of bold:

```
Inbox review — week of Mar 16:

TO CONFIRM (reply with numbers, e.g. "1,3"):
1. Archive 8 unread GitHub notification threads older than 30 days
2. Block sender newsletter@foo.com — 14 emails this week, all skipped by pulse
3. Block domain @promotions.shopify.com — 22 emails, no signal
4. Add *@linkedin.com to trusted senders — recruiter emails consistently landing in spam

REQUIRES EXPLICIT "delete N" (e.g. "delete 5"):
5. Delete 47 emails from noreply@promotions.shopify.com — all promotional, oldest from Jan

```

5. User confirms confirmable actions by number. User triggers delete actions by typing "delete N" explicitly. Claude executes each via `gws gmail` commands:
   - Block sender: update `email-prefs.md`, optionally create a Gmail filter
   - Block domain: update `email-prefs.md`
   - Bulk archive: `gws gmail users messages batchModify` with `ARCHIVE` action
   - Bulk delete: `gws gmail users messages batchDelete` — only executed when user types "delete N", never on a number or "all" alone
   - Trust sender/domain: update `email-prefs.md` trusted list

6. **After executing actions**, rewrite `pulse-log.md` in a single Write with the new cleanup entry appended to the log section (same atomic model as the pulse skill — never a partial append):
   ```
   [2026-03-16T08:30] CLEANUP: blocked newsletter@foo.com, blocked @promotions.shopify.com,
     archived 8 GitHub threads. Trusted linkedin.com for spam rescue.
   ```
   This ensures the next pulse run does not re-surface already-handled items.

### User-Controlled Actions Only

The inbox manager **never** deletes, blocks, or archives without explicit user confirmation. Delete actions are presented separately from confirmable actions — typing a number or "all" cannot trigger a delete. Only "delete N" (where N is the item number) executes a delete. "All" confirms all items in the confirmable group only.

---

## Scheduler Change — Empty Response Guard

One small change to `src/scheduler/scheduler.py` in `_run_task` to prevent empty Telegram messages from silent pulse runs:

```python
# Before fan-out, skip if agent returned nothing
if not response or not response.strip():
    log.info("scheduler: task %s returned empty response — no notifications sent", name)
    return
```

This is the minimal addition needed to support silent scheduled tasks. It benefits all future scheduled skills that may want to run silently under certain conditions.

---

## Memory Files

### `~/.open-assistant/memory/pulse-log.md`

Dual-purpose: state tracking (top) + history log (body). Written atomically in a single `Write` call per pulse run.

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

Claude's accumulated email intelligence. Created on first pulse run if it does not exist.

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

## Files Changed

| File | Change |
|------|--------|
| `schedules.yaml` | Add `pulse` and `inbox-manager` task entries |
| `src/scheduler/scheduler.py` | Add empty-response guard in `_run_task` |
| `src/channels/telegram.py` | Add `_inbox` handler and `CommandHandler("inbox", _inbox)` |
| `.claude/skills/pulse/SKILL.md` | New skill |
| `.claude/skills/inbox/SKILL.md` | New skill |
| `~/.open-assistant/memory/pulse-log.md` | Created on first pulse run |
| `~/.open-assistant/memory/email-prefs.md` | Created on first pulse run |

---

## Success Criteria

| Criterion | Observable signal |
|-----------|-----------------|
| No inbox gap on connection loss | Next pulse run covers from `last_successful_run`, not from 1h ago |
| Spam rescue works | Notable spam emails surface in Telegram with `[SPAM]` prefix |
| Silent when nothing notable | Pulse runs without Telegram message when only newsletters/noise |
| Inbox manager is non-destructive | No email is deleted or blocked without explicit user confirmation |
| Delete requires explicit word | Typing "1" or "all" cannot trigger a delete action |
| Pulse log stays current | After inbox manager cleanup, next pulse does not re-surface handled items |
| User can reference by number | Telegram notification uses numbered list; user replies with numbers only |
| Empty response not forwarded | Scheduler skips Telegram send when agent returns empty string |
