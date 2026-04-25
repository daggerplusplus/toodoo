# Data Model

## Schema

```
users
─────────────────────────────────────────
PK  id          INTEGER  AUTOINCREMENT
    username    TEXT     NOT NULL  UNIQUE
    pw_hash     TEXT     NOT NULL
    is_admin    INTEGER  NOT NULL  DEFAULT 0   (0|1; first registered user = 1)
    created_at  TEXT     NOT NULL  DEFAULT datetime('now')

invites
─────────────────────────────────────────
PK  token       TEXT
FK  created_by  INTEGER  → users.id
    created_at  TEXT     NOT NULL  DEFAULT datetime('now')
    used_at     TEXT                           (set when consumed)
FK  used_by     INTEGER  → users.id

categories
─────────────────────────────────────────
PK  id          INTEGER  AUTOINCREMENT
FK  user_id     INTEGER  NOT NULL  → users.id  ON DELETE CASCADE
    name        TEXT     NOT NULL
    sort_order  INTEGER  NOT NULL  DEFAULT 0
    created_at  TEXT     NOT NULL  DEFAULT datetime('now')

lists
─────────────────────────────────────────
PK  id          INTEGER  AUTOINCREMENT
FK  user_id     INTEGER  → users.id             (owner; NULL for unclaimed legacy rows)
FK  category_id INTEGER  → categories.id        ON DELETE SET NULL
    name        TEXT     NOT NULL
    icon        TEXT     NOT NULL  DEFAULT '📋'
    color       TEXT     NOT NULL  DEFAULT '#3b82f6'
    sort_order  INTEGER  NOT NULL  DEFAULT 0
    created_at  TEXT     NOT NULL  DEFAULT datetime('now')

list_members
─────────────────────────────────────────
FK  list_id     INTEGER  NOT NULL  → lists.id   ON DELETE CASCADE
FK  user_id     INTEGER  NOT NULL  → users.id   ON DELETE CASCADE
PK  (list_id, user_id)

tasks
─────────────────────────────────────────
PK  id            INTEGER  AUTOINCREMENT
FK  list_id       INTEGER  NOT NULL  → lists.id  ON DELETE CASCADE
    title         TEXT     NOT NULL
    notes         TEXT
    due_date      TEXT                            (YYYY-MM-DD or YYYY-MM-DDTHH:MM)
    priority      TEXT     NOT NULL  DEFAULT 'normal'
    done          INTEGER  NOT NULL  DEFAULT 0    (0|1)
    starred       INTEGER  NOT NULL  DEFAULT 0    (0|1)
    sort_order    INTEGER  NOT NULL  DEFAULT 0
    recurrence    TEXT                            (Nd|Nw|Nm|Ny, e.g. 1d, 2w, 3m, 1y; or legacy aliases daily|weekly|monthly|yearly)
    created_at    TEXT     NOT NULL  DEFAULT datetime('now')
    completed_at  TEXT                            (set when done=1; cleared on undo)

task_log
─────────────────────────────────────────
PK  id            INTEGER  AUTOINCREMENT
    task_id       INTEGER                         (soft ref; survives task deletion)
    task_title    TEXT     NOT NULL
    list_id       INTEGER                         (soft ref)
    list_name     TEXT     NOT NULL
    recurrence    TEXT
    due_date      TEXT
    cycles_late   INTEGER  NOT NULL  DEFAULT 0
    skipped       INTEGER  NOT NULL  DEFAULT 0    (0=completed, 1=skipped)
    reason        TEXT                            (populated on skips only)
    completed_at  TEXT     NOT NULL  DEFAULT datetime('now')

settings
─────────────────────────────────────────
PK  key         TEXT
    value       TEXT     NOT NULL
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
users       ──< categories    (user owns categories; deleted with user)
users       ──< lists         (user_id = owner)
lists       ──< list_members  (membership join; deleted with list or user)
users       ──< list_members
categories  ──< lists         (category_id; nulled on category delete)
lists       ──< tasks         (CASCADE delete)
tasks       ──< task_log      (soft ref; log survives task deletion)
```

## Notes

- All datetime columns are ISO-8601 `TEXT` — SQLite `date()` / `datetime()` functions work on them.
- `done`, `starred`, `is_admin`, `skipped` are stored as `0`/`1` integers (no boolean type in SQLite).
- `priority` valid values: `high`, `normal`, `low` — enforced by application, not a CHECK constraint.
- `recurrence` valid values: `Nd` / `Nw` / `Nm` / `Ny` where N is a positive integer (e.g. `1d`, `2w`, `14d`, `3m`, `1y`), or `NULL` — application enforced. Legacy aliases `daily`, `weekly`, `monthly`, `yearly` are accepted and map to `1d`, `1w`, `1m`, `1y` respectively.
- `list_members` is the authority for list visibility: a user sees a list iff there is a matching row.
- `sort_order` starts at 0 for all existing rows. New tasks created via API get `MAX(sort_order) + 1`.

## Default Seed Data

On first registration, `seed_for_user()` inserts three lists for the new user:

| name      | icon | color     |
|-----------|------|-----------|
| My Day    | ☀️   | #0ea5e9   |
| Important | ⭐   | #f43f5e   |
| Tasks     | 📋   | #6366f1   |

## Default Task Ordering Query

```sql
ORDER BY
  sort_order ASC,
  starred DESC,
  CASE priority WHEN 'high' THEN 0 WHEN 'normal' THEN 1 ELSE 2 END,
  due_date IS NULL, due_date ASC,
  created_at ASC
```

When all tasks have `sort_order = 0` (never manually reordered), the starred/priority/due secondary sort acts as the effective order, preserving pre-reorder behaviour.
