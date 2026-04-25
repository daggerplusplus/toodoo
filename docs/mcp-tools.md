# MCP Tools Reference

The MCP server (`mcp_server.py`) exposes the following tools over JSON-RPC stdio. It accesses the SQLite database directly — no HTTP, no session auth required.

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
Returns all lists ordered by `sort_order, id`, with a `pending` count per list.

**Input:** _(none)_

**Output:** array of list objects `{ id, name, icon, color, sort_order, created_at, pending }`

---

### create_list
Create a new list. Color is auto-assigned from the palette.

**Input:**
| Field | Type   | Required | Default |
|-------|--------|----------|---------|
| name  | string | yes      |         |
| icon  | string | no       | `📋`    |

---

### list_tasks
Get tasks, optionally filtered by list.

**Input:**
| Field        | Type    | Required | Default    |
|--------------|---------|----------|------------|
| list_id      | integer | no       | all lists  |
| include_done | boolean | no       | `false`    |
| sort         | string  | no       | `"default"` |

`sort` values: `"default"` (sort_order → starred → priority → due_date → created_at) or `"due_date"` (due_date ASC nulls last → starred → priority → created_at).

**Output:** array of task objects

---

### add_task
Add a task. New tasks are appended to the end of the list's manual order.

**Input:**
| Field      | Type    | Required | Default      |
|------------|---------|----------|--------------|
| title      | string  | yes      |              |
| list_id    | integer | no       | `3` (Tasks)  |
| notes      | string  | no       |              |
| due_date   | string  | no       | `YYYY-MM-DD` or `YYYY-MM-DDTHH:MM` |
| priority   | string  | no       | `"normal"`   |
| starred    | boolean | no       | `false`      |
| recurrence | string  | no       | `null`       |

`priority`: `high` | `normal` | `low`
`recurrence`: `Nd` / `Nw` / `Nm` / `Ny` where N is a positive integer (e.g. `1d`, `2w`, `14d`, `3m`, `1y`) | `null`
Legacy aliases `daily`, `weekly`, `monthly`, `yearly` are also accepted (map to `1d`, `1w`, `1m`, `1y`).

---

### complete_task
Mark a task done. For recurring tasks: advances `due_date` by one cycle (catching up missed cycles) and logs the completion — the task stays undone.

**Input:**
| Field | Type    | Required |
|-------|---------|----------|
| id    | integer | yes      |

---

### update_task
Partially update a task's fields.

**Input:**
| Field      | Type    | Required |
|------------|---------|----------|
| id         | integer | yes      |
| title      | string  | no       |
| notes      | string  | no       |
| due_date   | string  | no       | `YYYY-MM-DD` or `YYYY-MM-DDTHH:MM` |
| priority   | string  | no       |
| starred    | boolean | no       |
| recurrence | string  | no       |

`recurrence`: `Nd` / `Nw` / `Nm` / `Ny` where N is a positive integer (e.g. `1d`, `2w`, `14d`, `3m`, `1y`) | `null`
Legacy aliases `daily`, `weekly`, `monthly`, `yearly` are also accepted (map to `1d`, `1w`, `1m`, `1y`).

---

### delete_task
Permanently delete a task.

**Input:**
| Field | Type    | Required |
|-------|---------|----------|
| id    | integer | yes      |

---

### skip_task
Skip the current occurrence of a recurring task. Advances `due_date` identically to `complete_task` but logs `skipped=1`. Not valid for non-recurring tasks.

**Input:**
| Field  | Type    | Required |
|--------|---------|----------|
| id     | integer | yes      |
| reason | string  | no       |

---

### list_log
Return the activity log (completions and skips), newest first.

**Input:**
| Field | Type    | Required | Default |
|-------|---------|----------|---------|
| limit | integer | no       | `100`   |

**Output:** array of `task_log` rows — includes `skipped` (0/1) and `reason` fields.

---

### export_db
Export a full JSON snapshot of all lists, tasks, and task_log. Useful for backup or inspection.

**Input:** _(none)_

**Output:** same structure as `GET /api/export` — `{ version, exported_at, lists, tasks, task_log }`

---

## Testing the Server

```bash
echo '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"0"}}}' \
  | python mcp_server.py
```
