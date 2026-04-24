# Data Model

## Entity-Relationship Diagram

```
lists
─────────────────────────────────────────
PK  id          INTEGER  AUTOINCREMENT
    name        TEXT     NOT NULL
    icon        TEXT     NOT NULL  DEFAULT '📋'
    color       TEXT     NOT NULL  DEFAULT '#3b82f6'
    created_at  TEXT     NOT NULL  DEFAULT datetime('now')

tasks
─────────────────────────────────────────
PK  id            INTEGER  AUTOINCREMENT
FK  list_id       INTEGER  → lists.id  ON DELETE CASCADE
    title         TEXT     NOT NULL
    notes         TEXT
    due_date      TEXT                          (ISO-8601 date string)
    priority      TEXT     NOT NULL  DEFAULT 'normal'
    done          INTEGER  NOT NULL  DEFAULT 0  (0|1)
    starred       INTEGER  NOT NULL  DEFAULT 0  (0|1)
    recurrence    TEXT                          (daily|weekly|monthly|yearly)
    created_at    TEXT     NOT NULL  DEFAULT datetime('now')
    completed_at  TEXT                          (set when done=1; cleared on undo)

task_log
─────────────────────────────────────────
PK  id            INTEGER  AUTOINCREMENT
    task_id       INTEGER                       (soft ref to tasks.id — kept after delete)
    task_title    TEXT     NOT NULL
    list_id       INTEGER                       (soft ref)
    list_name     TEXT     NOT NULL
    recurrence    TEXT
    due_date      TEXT
    cycles_late   INTEGER  NOT NULL  DEFAULT 0
    completed_at  TEXT     NOT NULL  DEFAULT datetime('now')
```

## Indexes

```sql
idx_tasks_list    ON tasks(list_id)
idx_tasks_done    ON tasks(done)
idx_log_completed ON task_log(completed_at)
idx_log_task      ON task_log(task_id)
```

## Relationships

```
lists ──< tasks          (one list has many tasks; tasks deleted with list)
tasks ──< task_log       (soft reference; log rows survive task deletion)
```

## Notes

- All datetime columns are stored as ISO-8601 strings (`TEXT`) — SQLite's native date functions (`date()`, `datetime()`) work on these.
- `task_log` uses soft foreign keys so completion history is preserved even after the originating task is deleted.
- `done` and `starred` are stored as `0`/`1` integers (SQLite has no boolean type).
- `priority` is enforced by application logic, not a CHECK constraint: `high`, `normal`, `low`.
- `recurrence` is enforced by application logic: `daily`, `weekly`, `monthly`, `yearly`, or `NULL` for non-recurring.

## Default Seed Data

On a fresh database `init_db()` inserts three lists:

| id | name      | icon | color     |
|----|-----------|------|-----------|
| 1  | My Day    | ☀️   | #0ea5e9   |
| 2  | Important | ⭐   | #f43f5e   |
| 3  | Tasks     | 📋   | #6366f1   |

## Task Ordering Query

```sql
ORDER BY
  starred DESC,
  CASE priority WHEN 'high' THEN 0 WHEN 'normal' THEN 1 ELSE 2 END,
  created_at ASC
```
