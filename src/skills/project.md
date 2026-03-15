/project [name] — manage a life area or project using a structured project management approach.

Every life area is a project: relationship, fitness/health, work, professional projects, family & friends, German bureaucracy. Treat them all with the same rigour.

---

**If [name] is given:**

1. Read ~/.open-assistant/memory/projects.md and find the matching project.
2. Display its current status, next action, and any blockers.
3. Ask: "What's changed? Any progress, new blockers, or updated priorities?"
4. Update projects.md with the new information. Always overwrite the whole file — Read first, then Write.
5. Confirm: "Updated [project name] — next action is now: [new next action]."

---

**If no [name] is given — project dashboard:**

1. Read ~/.open-assistant/memory/projects.md and commitments.md.
2. Output a structured dashboard:

**Active projects**
For each project: name, status (on track / slipping / blocked), and next action.

**Attention needed**
Projects with no next action defined, or with status = blocked.

**Balance check**
Flag if any life area (relationship, fitness, family, creative) has no active project or hasn't been updated in the last 7 days.

3. End with: "Which project do you want to work on?"

---

**Adding a new project:**
If the user provides a project name that doesn't exist in projects.md, ask:
- "What life area does this belong to?" (relationship / fitness / work / professional / family / bureaucracy / other)
- "What's the goal — what does done look like?"
- "What's the first concrete action?"

Then add it to projects.md and confirm.

---

**Closing a project:**
If the user says a project is done, move it to a `## Archive` section at the bottom of projects.md with a completion date. Do not delete it.
