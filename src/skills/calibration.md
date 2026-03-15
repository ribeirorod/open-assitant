/calibration — establish or refresh the user's personal context.

Work through the following sections in order, asking one section at a time. Wait for the user's answer before moving on. Be conversational, not clinical.

---

**Section 1 — Projects**
Ask: "What are your active projects right now? For each one, what's the current status and the single most important next action?"
Write answers to ~/.open-assistant/memory/projects.md using this format:
```
## [Project Name]
**Status:** [one line]
**Priority:** [high/medium/low]
**Next action:** [one concrete step]
**Notes:** [anything else relevant]
```

---

**Section 2 — Commitments and deadlines**
Ask: "What are your fixed commitments in the next 3 months? Include personal milestones, work deadlines, and anything in German bureaucracy (tax, registrations, renewals)."
Write to ~/.open-assistant/memory/commitments.md and ~/.open-assistant/memory/german-life.md as appropriate.

---

**Section 3 — Procrastination**
Ask: "What have you been putting off? Name the things you keep thinking about but haven't started or finished. Be honest."
Write to ~/.open-assistant/memory/procrastination.md using format:
`- [YYYY-MM-DD added] Item description`
Use today's date for all new entries.

---

**Section 4 — Preferences**
Ask: "A few quick preferences so I can plan well for you:
- What time of day are you sharpest? (morning / afternoon / evening)
- Gym schedule — which days do you aim for?
- Piano practice — how often ideally?
- Communication style — bullet points or prose? Blunt or gentle?"
Write to ~/.open-assistant/memory/preferences.md.

---

**Section 5 — Confirm**
After all sections are filled, output a one-line summary of each memory file written, then say:
"Calibration complete. I know what matters to you — let's make this week count."

Do NOT write to memory during scheduled jobs. Only during interactive calibration or when the user explicitly shares new information.
