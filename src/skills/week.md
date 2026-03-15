/week — run the weekly overview workflow:
1. Read all files in ~/.open-assistant/memory/.
2. Use Bash to compute next Monday and Sunday in Europe/Berlin time:
   python3 -c "from datetime import datetime, timedelta; import zoneinfo; tz=zoneinfo.ZoneInfo('Europe/Berlin'); now=datetime.now(tz); offset=now.strftime('%z'); offset=offset[:3]+':'+offset[3:]; today=now.date(); monday=today+timedelta(days=(7-today.weekday())%7 or 7); sunday=monday+timedelta(days=6); print(monday.isoformat()+'T00:00:00'+offset, sunday.isoformat()+'T23:59:59'+offset)"
3. Run: gws calendar events list --params '{"calendarId":"primary","timeMin":"<MONDAY>","timeMax":"<SUNDAY>","singleEvents":true,"orderBy":"startTime"}'
4. Run: gws tasks tasks list --params '{"tasklist":"@default"}'
5. Output:
   - Days that look overloaded (>3 commitments)
   - Missing time blocks for: gym (need 3 sessions), family/relationship, piano
   - Suggested time blocks (list only — do NOT create calendar events)
   - One thing to defer if the week is too full
6. Ask: "Want me to create these blocks?" — only create after explicit confirmation.
