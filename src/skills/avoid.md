/avoid — surface procrastinated items:
1. Read ~/.open-assistant/memory/procrastination.md.
2. Run: gws tasks tasks list --params '{"tasklist":"@default"}' to find tasks with old due dates.
3. List avoided items by name with days elapsed (calculate from [YYYY-MM-DD added] in procrastination.md).
4. Ask: "Which one can you do 30 minutes on today?"
5. When user picks one:
   a. Compute current time in Berlin: python3 -c "from datetime import datetime; import zoneinfo; tz=zoneinfo.ZoneInfo('Europe/Berlin'); now=datetime.now(tz); print(now.strftime('%H:%M'), now.isoformat())"
   b. Run: gws calendar events list --params '{"calendarId":"primary","timeMin":"<NOW_ISO>","timeMax":"<END_OF_DAY_ISO>","singleEvents":true,"orderBy":"startTime"}' to find free slots.
   c. Identify first gap of ≥30 minutes. If none found or parsing unclear, ask: "What time works for you?"
   d. Propose: "I can block HH:MM–HH:MM for [item]. Confirm?"
   e. Only create the calendar event after explicit confirmation. Event title: "Focus: [item name]"
