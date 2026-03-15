---
name: note
description: Use when the user sends /note with any text, wants to capture something quickly, or mentions a task, reminder, goal, idea, habit, or personal fact they want saved. Invoke for any quick capture request — even vague ones like "remember that I..." or "add this...".
---

# Quick Capture

Receive whatever the user wants to save and route it to the right place without asking unnecessary questions.

## Routing logic

Determine the right destination based on content type:

| Content type | Destination |
|---|---|
| Task, reminder, deadline, thing to do | Google Tasks |
| Goal, preference, habit, personal fact | Relevant memory file |
| Both (e.g. "I want to practise piano more") | Both |

## Steps

**If it belongs in Google Tasks:**
Run: `gws tasks tasks insert --params '{"tasklist":"@default","requestBody":{"title":"<task>"}}'`

**If it belongs in memory:**
1. Read `~/.open-assistant/memory/index.md`.
2. Identify the most relevant file. If no file fits, create a new one and add an entry to `index.md`.
3. Read the target file, append the new entry, write it back.
   - For `procrastination.md` entries use format: `- [YYYY-MM-DD added] Item`

**If both apply:** do both.

## Confirm

End with one line: what was stored and where. Example:
> Added "Call Finanzamt" to Google Tasks and noted your piano goal in preferences.md.
