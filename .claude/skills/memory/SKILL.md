---
name: memory
description: Use when the user sends /memory, wants to see what the assistant knows about them, asks to view or manage their memory files, wants to archive old content, or asks about GDrive long-term memory. Invoke for any memory inspection or management request.
---

# Memory Management

Two-tier memory system: local files for fast access, GDrive for persistent shared storage.

## Tiers

| Tier | Location | Purpose |
|---|---|---|
| Local | `~/.open-assistant/memory/` | Active context, read every session |
| GDrive | `open_assistant/memory/` folder at Drive root | Shared persistent storage, synced automatically |

Memory is automatically synced between local and GDrive:
- **On startup**: latest files are pulled from GDrive.
- **After writes**: always trigger a push (see SYNC AFTER WRITES below).

This ensures memory persists across container restarts and rebuilds.

---

## Default (no subcommand)

1. Read `~/.open-assistant/memory/index.md`.
2. Read each listed file and produce a one-line summary.
3. Check if GDrive long-term memory is connected:
   ```
   gws drive files list --params '{"q":"name=\"open_assistant\" and mimeType=\"application/vnd.google-apps.folder\"","pageSize":1}'
   ```
4. Show: file list with summaries + GDrive status.
5. End with: "Use /memory show [topic], /memory update [topic], or /memory archive [topic]."

---

## Subcommands

**show [topic]** — Read the matching file and display its full contents.

**update [topic]** — Read file, ask what changed, write updated version back. Confirm changes.

**add [topic] [text]** — Append to the matching file. For `procrastination.md` prefix with today's date: `- [YYYY-MM-DD added] [text]`.

**archive [topic]** — Move stale content out of active memory:
- If GDrive `open_assistant/` folder exists: upload archived content as `archive-[topic].md` in that folder, then remove archived entries from the local file.
- If no GDrive: move content to a `## Archive` section at the bottom of the local file.
- Confirm what was moved and where.

---

## SYNC AFTER WRITES

**After every write to a memory file** (update, add, or archive), run:
```bash
cd /app && /app/.venv/bin/python -c "import asyncio; from src.memory.sync import push; asyncio.run(push(['FILENAME.md']))"
```
Replace `FILENAME.md` with the file(s) that were modified. This ensures memory survives the next container restart.
