---
name: update
description: Use when the user sends /update with a topic, wants to update their personal notes or memory, says something has changed about a project or commitment, or asks to edit a specific memory file. Invoke whenever targeted memory updates are requested.
---

# Update Memory

Update the memory file most relevant to the user's topic.

## Steps

1. Read `~/.open-assistant/memory/index.md`.
2. Identify the file that matches the topic. If ambiguous, pick the closest match and confirm.
3. Read the current contents of that file.
4. If the user hasn't already explained what changed, ask: "What's changed?"
5. Write the updated content back (overwrite the whole file — always Read first, then Write).
6. Confirm: "Updated [filename] — here's what changed: [1-2 line summary]."

## Guidelines

- Keep the existing structure and formatting of the file.
- For `procrastination.md`: if an item is resolved, remove it rather than just editing.
- For `projects.md`: update the status, next action, and notes fields for the relevant project.
- Never truncate or lose existing data — merge new information in.
