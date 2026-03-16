---
name: apple-reminders
description: Manage Apple Reminders — list, add, complete, and delete reminders via remindctl CLI. Use when the user mentions reminders, the Reminders app, or asks to be reminded of something with a due date synced to iPhone.
---

# Apple Reminders

Manage Apple Reminders via the `remindctl` CLI on macOS.

## Availability and permissions check

Before any command, verify remindctl is installed and authorised:

```bash
command -v remindctl || echo "remindctl not installed — run: brew install steipete/tap/remindctl"
remindctl status
```

If not installed or not authorised, tell the user and stop. To grant permission: `remindctl authorize`

## Disambiguation

If the user says "remind me" and the intent is ambiguous — no due date, or context suggests an in-chat alert rather than the Reminders app — ask:

> "Do you want this in Apple Reminders (syncs to your iPhone) or as a one-off message from me here?"

Only proceed once the intent is clear.

## Confirmation

Always confirm before creating, completing, or deleting a reminder. One sentence: "Ready to [action] — confirm?"

## Commands

**Check permissions**
```bash
remindctl status
```

**Today's reminders**
```bash
remindctl today
```

**Tomorrow**
```bash
remindctl tomorrow
```

**This week**
```bash
remindctl week
```

**Overdue**
```bash
remindctl overdue
```

**All reminders**
```bash
remindctl all
```

**List all lists**
```bash
remindctl list
```

**Add a reminder**
```bash
remindctl add --title "Task title" --list "List Name" --due "YYYY-MM-DD HH:mm"
```

Accepted due formats: `today`, `tomorrow`, `YYYY-MM-DD`, `YYYY-MM-DD HH:mm`, ISO 8601

**Edit a reminder**
```bash
remindctl edit <id> --title "New title" --due "YYYY-MM-DD HH:mm"
```

**Complete one or more reminders by ID**
```bash
remindctl complete <id1> <id2> <id3>
```

IDs come from the output of listing commands (hex format, e.g. `4A83`). Multiple IDs accepted in one call.

**Delete a reminder**
```bash
remindctl delete <id> --force
```

IDs come from listing output (hex format, e.g. `4A83`) — do not invent integer IDs.

**JSON output (for scripting)**
```bash
remindctl today --json
```

## Notes

- macOS only. Requires Reminders.app and permission (`remindctl authorize` on first use, `remindctl status` to check).
- IDs are hex identifiers shown in listing output — always retrieve them from `remindctl` output, never guess.
