# MCP Tools Reference

The MCP server (`mcp_server.py`) exposes the following tools over JSON-RPC stdio.

## Registration

`mcp-manager-entry.json` — update `cwd` and `TODO_DB` before deploying:
```json
{
  "command": "python",
  "args": ["mcp_server.py"],
  "cwd": "/path/to/toodoo",
  "env": { "TODO_DB": "/path/to/todo.db" }
}
```

## Tools

### list_lists
Returns all lists with pending task counts.

**Input:** _(none)_

**Output:** array of list objects `{ id, name, icon, color, created_at, pending }`

---

### create_list
Create a new list.

**Input:**
| Field | Type   | Required | Default |
|-------|--------|----------|---------|
| name  | string | yes      |         |
| icon  | string | no       | `📋`    |
| color | string | no       | auto    |

---

### list_tasks
Get tasks for a list.

**Input:**
| Field        | Type    | Required | Default |
|--------------|---------|----------|---------|
| list_id      | integer | yes      |         |
| include_done | boolean | no       | `false` |

**Output:** array of task objects, ordered: starred → priority → created_at

---

### add_task
Add a task to a list.

**Input:**
| Field      | Type    | Required | Default  |
|------------|---------|----------|----------|
| list_id    | integer | no       | `3` (Tasks) |
| title      | string  | yes      |          |
| notes      | string  | no       |          |
| due_date   | string  | no       | ISO-8601 date |
| priority   | string  | no       | `normal` |
| starred    | boolean | no       | `false`  |
| recurrence | string  | no       | `null`   |

---

### complete_task
Toggle a task's done state (same logic as the web toggle endpoint — respects recurrence).

**Input:**
| Field   | Type    | Required |
|---------|---------|----------|
| task_id | integer | yes      |

---

### update_task
Partially update a task.

**Input:**
| Field      | Type    | Required |
|------------|---------|----------|
| task_id    | integer | yes      |
| title      | string  | no       |
| notes      | string  | no       |
| due_date   | string  | no       |
| priority   | string  | no       |
| starred    | boolean | no       |
| recurrence | string  | no       |

---

### delete_task
Delete a task permanently.

**Input:**
| Field   | Type    | Required |
|---------|---------|----------|
| task_id | integer | yes      |

## Testing the Server

```bash
echo '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"0"}}}' \
  | python mcp_server.py
```
