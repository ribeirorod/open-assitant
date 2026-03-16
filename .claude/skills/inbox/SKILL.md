# Inbox Skill

You are running the inbox manager — weekly review and cleanup.

CONSTRAINTS:
- DO NOT write to any memory file other than pulse-log.md and email-prefs.md (email-prefs.md: append only — never overwrite existing entries, only add new lines).
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

DO NOT act until the user has replied to the triage report from Step 3.

Parse the user's reply:

For numbers or "all" (confirmable actions only):
- Archive threads:
  ```bash
  gws gmail users messages batchModify --params '{"userId":"me"}' --json '{"ids":["<id1>","<id2>",...],"removeLabelIds":["INBOX"]}'
  ```
- Block sender: use the Edit tool to append a new line to the Blocked Senders section of email-prefs.md with today's date (never use Write — append only)
- Block domain: use the Edit tool to append a new line to the Blocked Domains section of email-prefs.md with today's date (never use Write — append only)
- Trust sender/domain: use the Edit tool to append a new line to the Trusted Senders section of email-prefs.md with today's date and reason (never use Write — append only)

For "delete N" only (exact phrase with item number):
  ```bash
  gws gmail users messages batchDelete --params '{"userId":"me"}' --json '{"ids":["<id1>","<id2>",...]}'
  ```
  The "delete N" phrase is the confirmation — execute immediately. Do not ask for a second confirmation.

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
