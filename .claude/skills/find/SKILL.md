---
name: find
description: Locate a file on the local machine by name or content across ~/projects, ~/Downloads, ~/Documents. Optionally forward it via email.
---

# Find File

Search for a file on the local machine and optionally forward it by email.

The user's search query is provided as "User input:" at the end of this prompt.

## Step 1 — Name search

```bash
find ~/projects ~/Downloads ~/Documents -iname "*<query>*" 2>/dev/null
```

For each result, run `ls -lh <path>` and list as `path | size | modified`. Ask: "Which file did you mean?"

## Step 2 — Content search (only if Step 1 finds nothing)

```bash
grep -ril "<query>" ~/projects ~/Downloads ~/Documents 2>/dev/null
```

List matches with path. Ask: "Which file did you mean?"

## Step 3 — Not found

If still nothing: "No file matching `<query>` found in projects, Downloads, or Documents. Try a different keyword?"

## Step 4 — Forward (once user picks a file)

Ask: "Want to email this to someone?"

If yes: confirm recipient and subject, then use the `gws` skill to send. Always confirm before sending: "Ready to send `<filename>` to `<email>` — confirm?"
