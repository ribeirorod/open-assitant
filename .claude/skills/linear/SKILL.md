---
name: linear
description: Use when the user asks about Linear issues, projects, or team work — listing assigned issues, searching, creating, or updating issues.
---

# Linear Integration

Access Linear via the GraphQL API. The API key is in the `LINEAR_API_KEY` environment variable.

## API endpoint

```
https://api.linear.app/graphql
```

All requests are POST with:
- `Authorization: Bearer $LINEAR_API_KEY`
- `Content-Type: application/json`

## Routing

Parse the user's intent from the invocation args:

| Intent | Action |
|--------|--------|
| No args / "my issues" / "what's assigned" | → **My open issues** |
| "search [query]" | → **Search issues** |
| "create [title]" or clear creation intent | → **Create issue** |
| "team" or "all" | → **Team issues** |
| Issue ID (e.g. `ENG-123`) | → **Get single issue** |

---

## My open issues

```bash
curl -s -X POST https://api.linear.app/graphql \
  -H "Authorization: Bearer $LINEAR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "{ viewer { name assignedIssues(filter: { state: { type: { nin: [\"completed\", \"cancelled\"] } } }, orderBy: updatedAt) { nodes { id identifier title priority state { name } project { name } dueDate } } } }"
  }'
```

Present as a list grouped by priority (Urgent → High → Medium → No priority). Show: `identifier`, `title`, `state`, `project` (if set), `dueDate` (if set). Max 15 items then summarise.

Priority mapping: 0 = No priority, 1 = Urgent, 2 = High, 3 = Medium, 4 = Low.

---

## Search issues

```bash
curl -s -X POST https://api.linear.app/graphql \
  -H "Authorization: Bearer $LINEAR_API_KEY" \
  -H "Content-Type: application/json" \
  -d "{
    \"query\": \"{ issueSearch(query: \\\"SEARCH_TERM\\\", first: 10) { nodes { identifier title state { name } assignee { name } project { name } } } }\"
  }"
```

Replace `SEARCH_TERM` with the user's query. Present as a numbered list.

---

## Create issue

First, get available teams to let the user pick (or use the first/only team):

```bash
curl -s -X POST https://api.linear.app/graphql \
  -H "Authorization: Bearer $LINEAR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"query": "{ teams { nodes { id name } } }"}'
```

If there is only one team, use it directly. If multiple teams and the user did not specify, ask which team.

Then create the issue:

```bash
curl -s -X POST https://api.linear.app/graphql \
  -H "Authorization: Bearer $LINEAR_API_KEY" \
  -H "Content-Type: application/json" \
  -d "{
    \"query\": \"mutation { issueCreate(input: { teamId: \\\"TEAM_ID\\\", title: \\\"TITLE\\\", description: \\\"DESCRIPTION\\\" }) { success issue { identifier title url } } }\"
  }"
```

Always confirm before creating: show the title (and description if provided), then ask "Ready — confirm?"

On success, show the `identifier` and `url`.

---

## Get single issue

```bash
curl -s -X POST https://api.linear.app/graphql \
  -H "Authorization: Bearer $LINEAR_API_KEY" \
  -H "Content-Type: application/json" \
  -d "{
    \"query\": \"{ issue(id: \\\"IDENTIFIER\\\") { identifier title description state { name } assignee { name } priority project { name } dueDate createdAt updatedAt url } }\"
  }"
```

The `id` field accepts either the UUID or the human-readable identifier (e.g. `ENG-42`).

---

## Team issues (recent open)

```bash
curl -s -X POST https://api.linear.app/graphql \
  -H "Authorization: Bearer $LINEAR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "{ issues(filter: { state: { type: { nin: [\"completed\", \"cancelled\"] } } }, orderBy: updatedAt, first: 20) { nodes { identifier title priority state { name } assignee { name } project { name } } } }"
  }'
```

---

## Error handling

- If `LINEAR_API_KEY` is empty, respond: "Linear API key not configured — add `LINEAR_API_KEY` to `.env` and rebuild the container."
- If the API returns errors, show the `errors[0].message` clearly.
- Never expose the raw API key in responses.
