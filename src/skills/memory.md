/memory [subcommand] — inspect or update the personal knowledge base.

**Memory tiers:**
- **Local (fast):** ~/.open-assistant/memory/ — index.md + per-topic files. Always available.
- **GDrive (long-term):** If the user has granted Drive access, an `open_assistant/` folder at Drive root holds persistent/archived memory. Check for it with: `gws drive files list --params '{"q":"name=\"open_assistant\" and mimeType=\"application/vnd.google-apps.folder\"","pageSize":1}'`

Always start from local memory. Only touch GDrive when the user explicitly asks or when archiving old content.

---

Read ~/.open-assistant/memory/index.md first to get the file list.

If no subcommand is given, show a summary:
- List every local memory file with a one-line summary of its content.
- Note whether GDrive long-term memory is connected (check if open_assistant/ folder exists).
- End with: "Use /memory show [topic], /memory update [topic], or /memory archive [topic]."

---

**Subcommand: show [topic]**
Find the file in index.md that matches [topic]. Read and display its full contents.

---

**Subcommand: update [topic]**
Find the matching file, read its current contents, ask what's changed, then Write the updated version back. Confirm what changed.

---

**Subcommand: archive [topic]**
For content that's no longer active (completed projects, expired commitments):
1. Read the relevant local file.
2. If GDrive open_assistant/ folder exists: create or append to `open_assistant/archive-[topic].md` in Drive using `gws drive files create` or append via Docs API.
3. Remove the archived entries from the local file.
4. Confirm: "Archived [items] to GDrive open_assistant/archive-[topic].md and removed from local memory."
If GDrive is not connected, move content to a `## Archive` section at the bottom of the local file instead.

---

**Subcommand: add [topic] [text]**
Add the provided text as a new entry to the matching local memory file.
For procrastination.md, prefix with today's date: `- [YYYY-MM-DD added] [text]`
Confirm what was written.
