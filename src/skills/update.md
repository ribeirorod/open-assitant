/update {args} — update memory:
1. Read ~/.open-assistant/memory/index.md.
2. Read the memory file most relevant to the topic "{args}".
3. Ask what's changed (if the user hasn't already explained in this message).
4. Write the updated content back to the file using the Write tool.
5. Confirm: "Updated [filename] — here's what changed: ...".
