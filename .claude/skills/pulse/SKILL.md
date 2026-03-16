# Pulse Skill

You are running the hourly background email surveillance pulse.

CONSTRAINTS:
- DO NOT write to any memory file other than ~/.open-assistant/memory/pulse-log.md (except: create email-prefs.md if it does not exist — see Step 6).
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

If neither query returned any emails, proceed directly to Step 6 (write the log) then Step 7 (return empty — no notification).

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

Use the log content already read in Step 1 as the base. Do NOT re-read the file — use the snapshot from Step 1 to avoid overwriting entries added between reads.

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

If nothing was notable: produce no output at all. Do not write to chat, do not send a blank message, do not call any notification tool. Complete silently.
