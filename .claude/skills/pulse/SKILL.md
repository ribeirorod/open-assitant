# Pulse Skill

You are running the hourly background pulse — email surveillance and calendar update detection.

CONSTRAINTS:
- DO NOT write to any memory file other than ~/.open-assistant/memory/pulse-log.md (except: create email-prefs.md if it does not exist — see Step 7).
- DO NOT modify email-prefs.md if it already exists (read-only for pulse; first-run creation is the only exception).
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

Compute both the Unix epoch (for Gmail) and the ISO 8601 timestamp with offset (for Calendar):

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
    if dt.tzinfo is None:
        raise ValueError('naive timestamp')
    if (now - dt).total_seconds() > 86400:
        dt = now - timedelta(hours=24)
    if dt > now:
        dt = now - timedelta(hours=24)
except Exception:
    dt = now - timedelta(hours=24)

print(int(dt.timestamp()))           # line 1: Unix epoch for Gmail
print(dt.isoformat(timespec='seconds'))  # line 2: ISO with offset for Calendar
"
```

Record both values (needed in later steps and the log entry in Step 7).

## Step 2: Read email preferences

Read ~/.open-assistant/memory/email-prefs.md with the Read tool.

If the file does not exist, proceed with empty blocked/trusted lists. You will create it at the end of a successful run.

## Step 3: Query inbox (emails since last_successful_run)

```bash
gws gmail users messages list --params '{"q":"in:inbox after:<UNIX_EPOCH>","maxResults":50}'
```

For each message ID returned, fetch metadata — also capture the `threadId` from the response:

```bash
gws gmail users messages get --params '{"id":"<MESSAGE_ID>","format":"metadata","metadataHeaders":["From","Subject","Date"]}'
```

## Step 4: Detect replies to agent-sent threads

For each unique `threadId` collected in Step 3, fetch the full thread to check if any message in the thread bears the `SENT` label:

```bash
gws gmail users threads get --params '{"id":"<THREAD_ID>","format":"metadata","metadataHeaders":["From","Subject","Date"]}'
```

If the thread's `messages` array contains any message whose `labelIds` includes `"SENT"`, mark the corresponding inbox message as **REPLY_TO_SENT**. These messages bypass the normal significance filter in Step 6 — always NOTIFY.

## Step 5: Query SPAM (fixed 24h window)

```bash
gws gmail users messages list --params '{"q":"in:spam newer_than:1d","maxResults":30}'
```

Fetch metadata for each result the same way as Step 3.

## Step 6: Query calendar for updated events

```bash
gws calendar events list --params '{"calendarId":"primary","updatedMin":"<ISO_TIMESTAMP_WITH_OFFSET>","singleEvents":true,"showDeleted":true,"maxResults":50}'
```

Use the ISO timestamp from Step 1 (line 2) as `updatedMin`.

For each event returned, collect:
- `summary` (event title)
- `status` (`confirmed`, `cancelled`, `tentative`)
- `start.dateTime` or `start.date`
- `attendees` array (each entry has `email`, `displayName`, `responseStatus`)
- `updated` timestamp

Filter to events that are notable — skip events that have already ended more than 1 hour before now unless they were cancelled.

Classify each event update as one or more of:
- **CANCELLED** — `status` is `"cancelled"`
- **RSVP** — any attendee has `responseStatus` of `"accepted"`, `"declined"`, or `"tentative"` (skip `"needsAction"` — that's no change)
- **MODIFIED** — event is confirmed, not an RSVP-only change (time/location/title likely changed)

## Step 7: Atomic write to pulse-log.md

Compute the current timestamp in Europe/Berlin timezone:

```bash
python3 -c "from datetime import datetime; import zoneinfo; tz=zoneinfo.ZoneInfo('Europe/Berlin'); print(datetime.now(tz).isoformat(timespec='seconds'))"
```

Use the log content already read in Step 1 as the base. Do NOT re-read the file.

Rewrite ~/.open-assistant/memory/pulse-log.md entirely with the Write tool — a single write:

```
# Pulse Log

last_successful_run: <NEW_TIMESTAMP>

## Log

[<NEW_TIMESTAMP>] INBOX (since <PREVIOUS_TIMESTAMP>): <N> emails checked
  - REPLY: "<Subject> — reply from <Sender>" (for each REPLY_TO_SENT)
  - NOTIFIED: "<Subject> — <one-line summary>" (for other notable inbox items)
  - [SPAM] NOTIFIED: "<Subject> — <one-line summary>" (for spam rescues)
  - skipped: <N> (<brief reason e.g. newsletters, GitHub>)
[<NEW_TIMESTAMP>] CALENDAR (since <PREVIOUS_TIMESTAMP>): <N> events checked
  - CANCELLED: "<Event title>" on <date>
  - RSVP: "<Event title>" — <Name> <accepted|declined|tentative>
  - MODIFIED: "<Event title>" on <date> — updated
  - skipped: <N>

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

## Step 8: Judge significance and return result

**Email significance:**

ALWAYS NOTIFY:
- Messages marked REPLY_TO_SENT (regardless of sender or content)

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

**Calendar significance:**

ALWAYS NOTIFY:
- CANCELLED events (future events that were deleted or cancelled)
- RSVP: `"declined"` responses — someone said no
- RSVP: `"accepted"` responses for events with ≥3 attendees (quorum matters)
- MODIFIED: time or location changed on an event in the next 7 days

SKIP silently:
- `"tentative"` responses (noise, no action needed)
- `"accepted"` on 1:1 events (expected, not interesting)
- Events that already ended more than 1 hour ago

**Return format:**

If ≥1 item was notable, return a plain-text numbered list — no intro, no sign-off:

```
1. [REPLY] <Sender name> replied to "<Subject>" — <one-line description of what they said or asked>
2. [CALENDAR] "<Event title>" on <date> — <what changed: cancelled / X declined / X accepted / time changed to Y>
3. <Sender name/role> — <one-line description of other notable email>
4. [SPAM] <Sender> — <one-line description>
```

If nothing was notable: produce no output at all. Do not write to chat, do not send a blank message, do not call any notification tool. Complete silently.
