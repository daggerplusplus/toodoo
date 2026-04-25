# REST API Reference

Base URL: `http://localhost:8001`

All endpoints except `/api/health` require an authenticated session cookie (set by `POST /login`).

---

## Auth

### GET /api/me
Returns the current user.

**Response** `200`
```json
{ "id": 1, "username": "alice", "is_admin": 1, "created_at": "..." }
```

### POST /api/invite _(admin only)_
Generates a one-time invite link (valid 7 days).

**Response** `200` `{ "url": "http://localhost:8001/register?token=abc123" }` | `403`

---

## Lists

### GET /api/lists
Returns all lists the current user owns or is a member of, with a `pending` count of incomplete tasks. Own lists first, ordered by `sort_order ASC, id ASC`. Shared lists follow.

**Response** `200`
```json
[
  {
    "id": 1, "name": "My Day", "icon": "☀️", "color": "#0ea5e9",
    "user_id": 1, "category_id": null, "sort_order": 0,
    "created_at": "...", "pending": 3, "owner_username": "alice"
  }
]
```

### POST /api/lists
Create a new list. Color is auto-assigned from the palette if omitted.

**Body** `{ "name": "Work", "icon": "💼", "color": "#3b82f6" }`

**Response** `201` — created list object.

### PATCH /api/lists/{list_id} _(owner only)_
Update list metadata. All fields optional.

**Body** `{ "category_id": 2, "name": "Renamed", "icon": "🏠" }`

Set `category_id` to `null` to move a list out of its category.

**Response** `200` — updated list | `404`

### DELETE /api/lists/{list_id} _(owner only)_
Delete a list and all its tasks (CASCADE).

**Response** `204` | `404`

### POST /api/lists/reorder _(owner only)_
Set the display order of owned lists. IDs not belonging to the caller are silently ignored.

**Body** `{ "ids": [3, 1, 2] }`

**Response** `204`

---

## List Members (sharing)

### GET /api/lists/{list_id}/members _(owner only)_
**Response** `200` `[{ "id": 1, "username": "alice" }, ...]`

### POST /api/lists/{list_id}/members _(owner only)_
Add a user by username.

**Body** `{ "username": "bob" }`

**Response** `201` — `{ "id": 2, "username": "bob" }` | `404` user not found

### DELETE /api/lists/{list_id}/members/{user_id} _(owner only)_
Remove a member. Cannot remove the list owner.

**Response** `204` | `400` | `404`

---

## Categories

### GET /api/categories
Returns the current user's categories ordered by `sort_order ASC, name ASC`.

**Response** `200`
```json
[{ "id": 1, "name": "Work", "user_id": 1, "sort_order": 0, "created_at": "..." }]
```

### POST /api/categories
**Body** `{ "name": "Work" }`

**Response** `201` — created category object.

### PATCH /api/categories/{cat_id}
**Body** `{ "name": "New Name" }`

**Response** `200` — updated category | `404`

### DELETE /api/categories/{cat_id}
Delete a category. Member lists become uncategorized (`category_id → null`).

**Response** `204` | `404`

---

## Tasks

### GET /api/lists/{list_id}/tasks
**Query params**
- `include_done` (bool, default `false`)
- `sort` (`"default"` | `"due_date"`, default `"default"`)

**Ordering:**
- `default`: sort_order ASC → starred DESC → priority (high/normal/low) → due_date ASC (nulls last) → created_at ASC
- `due_date`: due_date ASC (nulls last) → starred DESC → priority → created_at ASC

**Response** `200` | `404`

### POST /api/lists/{list_id}/tasks
New tasks get `sort_order = MAX(existing) + 1`, appending them to the bottom of the manual order.

**Body**
```json
{
  "title": "Buy milk", "notes": "optional",
  "due_date": "2026-04-25", "priority": "normal",
  "starred": false, "recurrence": "weekly"
}
```
`priority`: `high` | `normal` | `low`
`recurrence`: `daily` | `weekly` | `monthly` | `yearly` | `null`

**Response** `201` | `404`

### POST /api/lists/{list_id}/tasks/reorder
**Body** `{ "ids": [3, 1, 2] }`

**Response** `204` | `404`

### PATCH /api/tasks/{task_id}
Partial update. Accepts `title`, `notes`, `due_date`, `priority`, `starred`, `recurrence`, `list_id` (move task).

**Response** `200` | `404`

### DELETE /api/tasks/{task_id}
**Response** `204` | `404`

### DELETE /api/lists/{list_id}/tasks/completed
Delete all done tasks from a list. Log entries are preserved.

**Response** `200` `{ "cleared": 3 }` | `404`

---

## Task Actions

### POST /api/tasks/{task_id}/toggle
Toggle done/undone. Recurring tasks: advances `due_date` by one cycle, logs the completion, stays undone.

**Response** `200` — updated task | `404`

### POST /api/tasks/{task_id}/star
Toggle starred.

**Response** `200` — updated task | `404`

### POST /api/tasks/{task_id}/skip
Skip current occurrence of a recurring task (advances `due_date`, logs `skipped=1`). Not valid for non-recurring tasks.

**Body** (optional) `{ "reason": "too busy" }`

**Response** `200` | `400` not recurring | `404`

---

## Log

### GET /api/log
**Query params** `limit` (int, default `500`)

**Response** `200`
```json
[{
  "id": 1, "task_id": 7, "task_title": "Weekly chore",
  "list_id": 3, "list_name": "Tasks", "recurrence": "weekly",
  "due_date": "2026-04-14", "cycles_late": 1,
  "skipped": 0, "reason": null, "completed_at": "2026-04-21T10:00:00"
}]
```

---

## Export / Import

### GET /api/export
Full JSON snapshot as a file download (`toodoo-backup.json`).

**Response** `200 application/json`
```json
{ "version": 1, "exported_at": "...", "lists": [...], "tasks": [...], "task_log": [...] }
```

### POST /api/import
Replaces all data. **Destructive.** Requires `"version": 1`.

**Response** `200` `{ "imported": { "lists": 3, "tasks": 12, "task_log": 5 } }` | `422`

---

## Health

### GET /api/health _(no auth required)_
**Response** `200` `{ "status": "ok", "auth": true }`

---

## UI

### GET /
Serves `static/index.html`.
