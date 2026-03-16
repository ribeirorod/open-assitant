---
name: apple-notes
description: Manage Apple Notes — create, search, list, and export notes via the memo CLI. Use when the user mentions notes, Apple Notes, or asks to jot something down.
---

# Apple Notes

Manage Apple Notes via the `memo` CLI on macOS.

## Availability check

Before any command, verify memo is installed:

```bash
command -v memo || echo "memo not installed — run: brew tap antoniorodr/memo && brew install antoniorodr/memo/memo"
```

If not installed, tell the user and stop.

## Confirmation

Always confirm with the user before creating a note. One sentence: "Ready to [action] — confirm?"

## Commands

**List all notes**
```bash
memo notes
```

**Filter by folder**
```bash
memo notes -f "Folder Name"
```

**Search notes (interactive fuzzy search)**
```bash
memo notes -s
```
Note: `-s` launches interactive fuzzy search — no inline query string is supported.

**Create a note (interactive)**
```bash
memo notes -a
```
Note: `-a` opens an interactive editor. It does not accept a title argument on the command line.

**Export to HTML/Markdown (interactive)**
```bash
memo notes -ex
```

## Limitations — Bot context

The following commands are interactive and require terminal input. **Never run them directly in bot context.** Instead, tell the user to run them manually in a terminal:

- `memo notes -e` — edit a note
- `memo notes -d` — delete a note
- `memo notes -m` — move note to folder
- `memo notes -a` — create a note (interactive editor)
- `memo notes -s` — search (interactive fuzzy)

For bot-triggered note creation, inform the user that `memo` requires interactive input and suggest they run it in a terminal.

## Other limitations

- Cannot edit notes that contain images or attachments.
- macOS only. Requires Notes.app and Automation permission (System Settings → Privacy & Security → Automation).
