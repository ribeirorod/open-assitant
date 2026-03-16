---
name: plan
description: Use when the user sends /plan, asks for today's priorities, wants a daily plan, or asks what to focus on today. Invoke whenever daily planning, morning briefing, or "what should I do today" is requested.
---

# Daily Planning

Read memory and live data, then synthesise a focused, realistic plan for today.

## Steps

1. Read `~/.open-assistant/memory/index.md`, then read `projects.md`, `commitments.md`, `preferences.md`, and `procrastination.md`.
2. Run: `gws calendar +agenda` — get today's events.
3. Run: `gws gmail +triage` — surface unread emails needing action.
4. Run: `gws tasks tasks list --params '{"tasklist":"@default"}'` — get open tasks.

## Output format

**Today's 3 priorities**
Pick the three most impactful things given the calendar load. Bold them. Never more than three — if the user listed more, say which one to drop.

**Emails needing action** (max 3)
One line each: sender / subject → suggested next step.

**One thing to face today**
The oldest item in `procrastination.md` that is more than 3 days old. Name it directly. If nothing qualifies, skip this section.

---

End with: "Does this look right?"

Keep the full response under 15 lines. No filler, no emoji.
