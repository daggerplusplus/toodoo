# REST API Reference

Base URL: `http://localhost:8001`

## Lists

### GET /api/lists
Returns all lists with a `pending` count of incomplete tasks.

**Response** `200`
```json
[
  { "id": 1, "name": "My Day", "icon": "☀️", "color": "#0ea5e9", "created_at": "...", "pending": 3 }
]
```

### POST /api/lists
Create a new list. Color is auto-assigned if omitted.

**Body**
```json
{ "name": "Work", "icon": "💼", "color": "#3b82f6" }
```
**Response** `201` — the created list object.

### DELETE /api/lists/{list_id}
Delete a list and all its tasks (CASCADE).

**Response** `204` | `404`

---

## Tasks

### GET /api/lists/{list_id}/tasks
Returns tasks for a list. Excludes completed tasks by default.

**Query params**
- `include_done` (bool, default `false`) — include completed tasks
- `sort` (string, default `"default"`) — `"default"` or `"due_date"`

**Ordering:**
- `default`: starred → priority (high/normal/low) → due_date ASC (nulls last) → created_at ASC
- `due_date`: due_date ASC (nulls last) → starred → priority → created_at ASC

**Response** `200` | `404`

### POST /api/lists/{list_id}/tasks
Create a task in a list.

**Body**
```json
{
  "title": "Buy milk",
  "notes": "optional",
  "due_date": "2026-04-25",
  "priority": "normal",
  "starred": false,
  "recurrence": "weekly"
}
```
`priority` values: `high` | `normal` | `low`  
`recurrence` values: `daily` | `weekly` | `monthly` | `yearly` | `null`

**Response** `201` | `404`

### PATCH /api/tasks/{task_id}
Update any subset of task fields (partial update).

**Body** — all fields optional: `title`, `notes`, `due_date`, `priority`, `starred`, `recurrence`

**Response** `200` | `404`

### DELETE /api/tasks/{task_id}
**Response** `204` | `404`

### DELETE /api/lists/{list_id}/tasks/completed
Delete all completed (`done=1`) tasks from a list. Task log entries are **not** affected — history is preserved.

**Response** `200`
```json
{ "cleared": 3 }
```
`cleared` is the number of tasks deleted. Returns `404` if the list doesn't exist.

---

## Task Actions

### POST /api/tasks/{task_id}/toggle
Toggle done/undone. Special behaviour for recurring tasks: advances `due_date` by one cycle (catching up missed cycles) and logs the completion — the task itself stays undone.

**Response** `200` — updated task | `404`

### POST /api/tasks/{task_id}/star
Toggle starred state.

**Response** `200` — updated task | `404`

### POST /api/tasks/{task_id}/skip
Skip the current occurrence of a recurring task. Advances `due_date` by one cycle (catching up missed cycles, same as toggle) and writes a skip entry to `task_log`. Only valid for recurring tasks.

**Body** — all fields optional:
```json
{ "reason": "too busy today" }
```

**Response** `200` — updated task | `400` task is not recurring | `404`

---

## Log

### GET /api/log
Returns completion history from `task_log`.

**Query params**
- `limit` (int, default `500`)

**Response** `200`
```json
[
  {
    "id": 1,
    "task_id": 7,
    "task_title": "Weekly chore",
    "list_id": 3,
    "list_name": "Tasks",
    "recurrence": "weekly",
    "due_date": "2026-04-14",
    "cycles_late": 1,
    "completed_at": "2026-04-21T10:00:00"
  }
]
```

---

## Export / Import

### GET /api/export
Returns a full JSON snapshot of all data, as a file download.

**Response** `200 application/json` (with `Content-Disposition: attachment; filename=toodoo-backup.json`)
```json
{
  "version": 1,
  "exported_at": "2026-04-22T18:00:00+00:00",
  "lists": [...],
  "tasks": [...],
  "task_log": [...]
}
```

### POST /api/import
Replaces all data from a previously exported JSON snapshot. **Destructive** — all existing data is deleted before restore.

**Body** — same structure as the export response (must include `"version": 1`).

**Response** `200`
```json
{ "imported": { "lists": 3, "tasks": 12, "task_log": 5 } }
```
**Response** `422` — if `version` is not `1` or payload is malformed.

---

## UI

### GET /
Serves `static/index.html` — the single-page app.
