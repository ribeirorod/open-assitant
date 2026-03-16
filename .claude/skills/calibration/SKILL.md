---
name: calibration
description: Use when the user sends /calibration, is setting up the assistant for the first time, wants to do a full context refresh, or says they want to update their goals, projects, and preferences comprehensively. Also invoke if memory files are missing or clearly stale.
---

# Calibration

Build or refresh the user's full personal context through structured conversation. Work through sections one at a time — wait for each answer before moving on.

## Section 1 — Projects

Ask: "What are your active projects right now? For each one: what's the status and the single most important next action?"

Write to `~/.open-assistant/memory/projects.md`:
```
## [Project Name]
**Area:** [relationship / fitness / work / professional / family / bureaucracy]
**Status:** [one line]
**Priority:** [high / medium / low]
**Next action:** [one concrete step]
```

---

## Section 2 — Commitments and deadlines

Ask: "What are your fixed commitments in the next 3 months? Include personal milestones, work deadlines, and German bureaucracy items (tax, registrations, renewals)."

Write personal and work commitments to `commitments.md`. Write German bureaucracy items to `german-life.md`.

---

## Section 3 — Procrastination

Ask: "What have you been putting off? Things you keep meaning to do but haven't started or finished. Be honest."

Write to `procrastination.md` using format: `- [YYYY-MM-DD added] Item description`
Use today's date for all new entries.

---

## Section 4 — Preferences

Ask: "A few quick questions so I can plan well for you:
- What time of day are you sharpest?
- Gym — which days do you aim for?
- Piano practice — how often ideally?
- Communication style — bullet points or prose? Blunt or warm?"

Write to `preferences.md`.

---

## Section 5 — Confirm

After all sections, output a one-line summary per file written, then close with:
"Calibration complete. I know what matters to you — let's make this week count."

Create `index.md` if it doesn't exist, listing all files with one-line descriptions.
