---
name: week
description: Use when the user sends /week, asks about the upcoming week, wants a weekly overview, wants to plan next week, or asks about calendar load for the week ahead. Invoke whenever weekly planning or scheduling review is requested.
---

# Weekly Overview

Read memory and next week's calendar, identify gaps and overload, suggest protected time blocks.

## Steps

1. Read all files in `~/.open-assistant/memory/`.
2. Compute next Monday and Sunday in Europe/Berlin time:
   ```
   python3 -c "from datetime import datetime, timedelta; import zoneinfo; tz=zoneinfo.ZoneInfo('Europe/Berlin'); now=datetime.now(tz); offset=now.strftime('%z'); offset=offset[:3]+':'+offset[3:]; today=now.date(); monday=today+timedelta(days=(7-today.weekday())%7 or 7); sunday=monday+timedelta(days=6); print(monday.isoformat()+'T00:00:00'+offset, sunday.isoformat()+'T23:59:59'+offset)"
   ```
3. Run: `gws calendar events list --params '{"calendarId":"primary","timeMin":"<MONDAY>","timeMax":"<SUNDAY>","singleEvents":true,"orderBy":"startTime"}'`
4. Run: `gws tasks tasks list --params '{"tasklist":"@default"}'`

## Output format

**Overloaded days** — flag any day with more than 3 commitments.

**Missing protected time** — check for:
- Gym (need at least 3 slots this week)
- Family / relationship time
- Piano practice

**Suggested time blocks** — list specific slots (day + time). Do NOT create calendar events yet.

**One thing to defer** — if the week looks too full, name the one thing to push.

---

End with: "Want me to create these blocks?" — only create events after the user explicitly confirms.
