---
name: memory
description: Use when the user sends /memory, wants to see what the assistant knows about them, asks to view or manage their memory files, wants to archive old content, or asks about GDrive long-term memory. Invoke for any memory inspection or management request.
---

# Memory Management

Two-tier memory system: local files for fast access, GDrive for long-term archiving.

## Tiers

| Tier | Location | Purpose |
|---|---|---|
| Local | `~/.open-assistant/memory/` | Active context, read every session |
| GDrive | `open_assistant/` folder at Drive root | Archive, long-term reference |

Always start from local. Only touch GDrive when the user asks or when archiving.

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
