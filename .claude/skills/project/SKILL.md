---
name: project
description: Use when the user sends /project, wants a project dashboard, asks about the status of a life area, wants to add or update a project, or mentions tracking progress on relationship, fitness, work, family, or German bureaucracy goals. Invoke whenever life-as-project management is needed.
---

# Project Management

Every life area is a project. Treat them all with the same rigour: status, next action, blockers.

**Life areas:** relationship · fitness/health · work · professional projects · family & friends · German bureaucracy

---

## With a project name

1. Read `~/.open-assistant/memory/projects.md`, find the matching project.
2. Show current status, next action, and blockers.
3. Ask: "What's changed?"
4. Update `projects.md` (Read first, then Write the whole file).
5. Confirm: "Updated [name] — next action is now: [new next action]."

---

## No name given — dashboard

1. Read `projects.md` and `commitments.md`.
2. Output:

**Active projects**
For each: name · status (on track / slipping / blocked) · next action.

**Needs attention**
Projects with no next action defined, or status = blocked.

**Balance check**
Flag any life area with no active project or no update in the last 7 days.

End with: "Which project do you want to work on?"

---

## Adding a new project

If the name doesn't exist, ask:
- "Which life area?" (relationship / fitness / work / professional / family / bureaucracy)
- "What does done look like?"
- "What's the first concrete action?"

Add to `projects.md`, confirm.

---

## Closing a project

Move the project to a `## Archive` section at the bottom of `projects.md` with a completion date. Never delete.
