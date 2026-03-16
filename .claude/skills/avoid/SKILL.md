---
name: avoid
description: Use when the user sends /avoid, mentions procrastination, says they've been putting something off, wants to face avoided tasks, or asks what they keep avoiding. Invoke whenever surfacing or scheduling procrastinated items is needed.
---

# Face What You've Been Avoiding

Surface procrastinated items with honest age tracking, then find a concrete time slot today.

## Steps

1. Read `~/.open-assistant/memory/procrastination.md`.
2. Run: `gws tasks tasks list --params '{"tasklist":"@default"}'` — find tasks with overdue dates.
3. Calculate days elapsed for each item in `procrastination.md` using the `[YYYY-MM-DD added]` timestamp.
4. List avoided items: name + days avoided. Oldest first.
5. Ask: "Which one can you do 30 minutes on today?"

## When the user picks one

a. Get current Berlin time:
   ```
   python3 -c "from datetime import datetime; import zoneinfo; tz=zoneinfo.ZoneInfo('Europe/Berlin'); now=datetime.now(tz); print(now.strftime('%H:%M'), now.isoformat())"
   ```
b. Get remaining events today:
   ```
   gws calendar events list --params '{"calendarId":"primary","timeMin":"<NOW_ISO>","timeMax":"<END_OF_DAY_ISO>","singleEvents":true,"orderBy":"startTime"}'
   ```
c. Find the first gap of ≥30 minutes. If none exists or parsing fails, ask: "What time works for you?"
d. Propose: "I can block HH:MM–HH:MM for [item]. Confirm?"
e. Only after explicit confirmation: create the event with title `Focus: [item name]`.
