# Knowledge Graph

Entities, their attributes, and relationships in this codebase — structured for AI consumption.

## Entities

### Module: web.py
- **type:** FastAPI application
- **serves:** REST API + static SPA
- **depends_on:** db.py
- **exposes:** HTTP routes at `/api/*`, UI at `/`
- **key_logic:** `_missed_cycles()` — recurrence advancement; `_own_list()` / `_member_list()` — access control tiers

### Module: mcp_server.py
- **type:** MCP stdio server
- **protocol:** JSON-RPC 2.0 over stdin/stdout
- **depends_on:** db.py
- **exposes:** tools: list_lists, create_list, list_tasks, add_task, complete_task, update_task, delete_task, skip_task, list_log, export_db
- **note:** bypasses HTTP auth — accesses DB directly; single-user assumption
- **logging:** stderr only (stdout reserved for MCP wire protocol)

### Module: db.py
- **type:** shared database layer
- **engine:** SQLite (WAL mode, foreign keys ON)
- **config:** `TODO_DB` env var → defaults to `todo.db` beside script
- **exports:** get_conn, init_db, seed_for_user, row_to_dict, next_color, hash_pw, verify_pw, export_data, LIST_COLORS

### Table: users
- **columns:** id, username (UNIQUE), pw_hash, is_admin, created_at
- **first_user:** automatically `is_admin=1`
- **auth:** passwords hashed with `hashlib.scrypt`; sessions via `itsdangerous` signed cookies

### Table: invites
- **columns:** token (PK), created_by→users, created_at, used_at, used_by→users
- **validity:** 7 days from `created_at`; single-use (`used_at` set on consumption)

### Table: categories
- **columns:** id, user_id→users (CASCADE), name, sort_order, created_at
- **purpose:** user-owned groupings for lists shown in the sidebar
- **on_delete:** deleting a category NULLs `lists.category_id` for member lists

### Table: lists
- **columns:** id, user_id→users (owner), category_id→categories (nullable), name, icon, color, sort_order, created_at
- **access:** controlled via `list_members`; `user_id` is the owner
- **sort_order:** manual display position within category or uncategorized group

### Table: list_members
- **columns:** (list_id, user_id) composite PK
- **purpose:** join table for list sharing — a user sees a list iff a row exists here
- **seeded:** populated on list creation and on `seed_for_user()`

### Table: tasks
- **columns:** id, list_id (CASCADE), title, notes, due_date, priority, done, starred, sort_order, recurrence, created_at, completed_at
- **sort_order:** manual position within list; new tasks get `MAX(sort_order)+1`
- **priority_values:** high | normal | low
- **recurrence_values:** daily | weekly | monthly | yearly | null

### Table: task_log
- **columns:** id, task_id (soft), task_title, list_id (soft), list_name, recurrence, due_date, cycles_late, skipped (0/1), reason, completed_at
- **purpose:** immutable history of completions (`skipped=0`) and skips (`skipped=1`)

### Table: settings
- **columns:** key (PK), value
- **used_for:** `session_secret` key (auto-generated on first boot)

### Frontend: static/index.html
- **type:** single-page app
- **tech:** vanilla JS, no framework, no build step
- **state:** `lists`, `tasks`, `categories`, `currentUser`, `activeListId`, `activeView`, `showDone`, `sortMode`, `expandedTaskId`, `collapsedCategories` (Set, persisted to localStorage), `darkMode`, `sidebarCollapsed`
- **renders:** `renderSidebar()`, `renderTasks()` — full re-render on each change
- **drag:** Pointer Events API (`pointerdown/move/up`) — unified mouse + touch reorder for lists and tasks

## Relationships

```
web.py          --imports-->    db.py
mcp_server.py   --imports-->    db.py
web.py          --serves-->     static/index.html
users           --owns-->       categories         (CASCADE delete)
users           --owns-->       lists              (user_id)
categories      --groups-->     lists              (category_id; NULL on delete)
lists           --has many-->   list_members
users           --has many-->   list_members
lists           --has many-->   tasks              (CASCADE delete)
tasks           --logs to-->    task_log           (soft ref; history survives delete)
```

## Behavioural Rules

| Rule | Location |
|------|----------|
| First registered user becomes `is_admin=1` | `register_submit()` in web.py |
| Only admins can create invite links | `create_invite()` in web.py |
| Invites expire after 7 days and are single-use | `_valid_invite()` in web.py |
| A user sees a list iff `list_members` has a row for them | `_member_list()` in web.py |
| Owner-only operations (delete list, manage members, reorder, patch) use `_own_list()` | web.py |
| Recurring task toggle/skip advances `due_date` by `missed+1` cycles; task stays undone | `toggle_task()`, `skip_task()` in web.py |
| `cycles_late` = periods elapsed since `due_date` before action | `_missed_cycles()` in web.py |
| Non-recurring task toggle sets `done=1` + `completed_at` | `toggle_task()` in web.py |
| Undo (toggle when `done=1`) clears `done` and `completed_at`, no log entry | `toggle_task()` in web.py |
| Skip logs `skipped=1`; toggle logs `skipped=0` | `skip_task()` / `toggle_task()` in web.py |
| Default task sort: sort_order ASC → starred DESC → priority → due_date ASC (nulls last) → created_at ASC | `get_tasks()` in web.py |
| `sort=due_date` sort: due_date ASC (nulls last) → starred → priority → created_at | `get_tasks()` in web.py |
| New tasks get `sort_order = MAX(existing)+1` in their list | `add_task()` in web.py, `add_task` in mcp_server.py |
| When all tasks have `sort_order=0`, secondary sort (starred/priority) acts as effective order | query design |
| Deleting a category NULLs `category_id` on all its lists | `delete_category()` in web.py |
| Color auto-assigned cycling through `LIST_COLORS` by count of user's existing lists | `next_color()` in db.py |
| MCP `add_task` defaults `list_id` to `3` (seeded Tasks list) | mcp_server.py |
| Dark mode persisted to `localStorage`; applied via `body.dark` CSS class | `applyDark()` in index.html |
| Category collapse state persisted to `localStorage` as JSON array of IDs | `toggleCategory()` in index.html |

## File Map

```
toodoo/
├── web.py                  # FastAPI app + REST routes
├── db.py                   # SQLite shared layer
├── mcp_server.py           # MCP stdio server
├── static/
│   └── index.html          # SPA frontend
├── tests/
│   ├── conftest.py         # pytest fixtures (tmp_db, client with auth)
│   ├── test_db.py          # db.py unit tests
│   ├── test_web.py         # REST API integration tests
│   └── test_missed_cycles.py  # recurrence logic parametrized tests
├── docs/
│   ├── api.md              # REST API reference
│   ├── architecture.md     # Architecture overview + diagrams
│   ├── data-model.md       # Full schema + relationships
│   ├── mcp-tools.md        # MCP tools reference
│   └── knowledge-graph.md  # This file
├── mcp-manager-entry.json  # MCP registration config
├── requirements.txt
└── todo.db                 # Runtime database (gitignored)
```
