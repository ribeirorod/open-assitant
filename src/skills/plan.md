/plan — run the daily planning workflow:
1. Read ~/.open-assistant/memory/index.md then projects.md, commitments.md, preferences.md, procrastination.md.
2. Run: gws calendar +agenda
3. Run: gws gmail +triage
4. Run: gws tasks tasks list --params '{"tasklist":"@default"}'
5. Produce a structured daily plan:
   **Today's 3 priorities** (realistic given the calendar — no more than 3, bold them)
   **Emails needing action** (max 3, one line each with suggested next step)
   **One item to face today** (oldest item in procrastination.md by added date, if any >3 days old)
6. Ask: "Does this look right?"
Max 15 lines.
