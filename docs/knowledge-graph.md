# Knowledge Graph

Entities, their attributes, and relationships in this codebase — structured for AI consumption.

## Entities

### Module: web.py
- **type:** FastAPI application
- **serves:** REST API + static SPA
- **depends_on:** db.py
- **exposes:** HTTP routes at `/api/*`, UI at `/`
- **key_logic:** `_missed_cycles()` — recurrence advancement algorithm

### Module: mcp_server.py
- **type:** MCP stdio server
- **protocol:** JSON-RPC 2.0 over stdin/stdout
- **depends_on:** db.py
- **exposes:** MCP tools (list_lists, create_list, list_tasks, add_task, complete_task, update_task, delete_task)
- **logging:** stderr only (stdout reserved for MCP wire protocol)

### Module: db.py
- **type:** shared database layer
- **engine:** SQLite (WAL mode, foreign keys ON)
- **config:** `TODO_DB` env var → defaults to `todo.db` beside script
- **exports:** get_conn, init_db, row_to_dict, next_color, LIST_COLORS

### Table: lists
- **columns:** id, name, icon, color, created_at
- **seeded_with:** My Day (☀️), Important (⭐), Tasks (📋)
- **child_of:** _(root entity)_

### Table: tasks
- **columns:** id, list_id, title, notes, due_date, priority, done, starred, recurrence, created_at, completed_at
- **parent:** lists (ON DELETE CASCADE)
- **priority_values:** high | normal | low
- **recurrence_values:** daily | weekly | monthly | yearly | null

### Table: task_log
- **columns:** id, task_id, task_title, list_id, list_name, recurrence, due_date, cycles_late, completed_at, skipped, reason
- **purpose:** immutable completion and skip history; survives task deletion (soft FK)
- **written_by:** toggle endpoint (completions, `skipped=0`), skip endpoint (skips, `skipped=1`)

### Frontend: static/index.html
- **type:** single-page app
- **tech:** vanilla JS, no framework, no build step
- **state:** module-level variables: `lists`, `tasks`, `activeListId`, `activeView`, `showDone`, `sortMode`, `expandedTaskId`, `darkMode`
- **renders:** renderSidebar(), renderTasks() — full re-render on each change
- **dark_mode:** `body.dark` class + CSS variable overrides; toggled by moon/sun button; persisted in `localStorage`

## Relationships

```
web.py          --imports-->  db.py
mcp_server.py   --imports-->  db.py
web.py          --serves-->   static/index.html
lists           --has many--> tasks            (CASCADE delete)
tasks           --logs to-->  task_log         (soft ref; history survives delete)
toggle_task()   --writes-->   task_log
toggle_task()   --calls-->    _missed_cycles()
```

## Behavioural Rules

| Rule | Location |
|------|----------|
| Recurring task toggle advances `due_date`, does not set `done=1` | `toggle_task()` in web.py |
| Recurring task skip advances `due_date` identically to toggle but logs `skipped=1` + optional `reason` | `skip_task()` in web.py |
| `task_log.skipped`: 0 = completed, 1 = skipped; `task_log.reason`: nullable, only populated on skips | task_log table |
| `cycles_late` = periods elapsed since `due_date` before completion | `_missed_cycles()` in web.py |
| `due_date` advanced by `missed + 1` cycles using SQLite `date()` | `toggle_task()` in web.py |
| Non-recurring task toggle sets `done=1` + `completed_at` | `toggle_task()` in web.py |
| Undo (toggle when done=1) clears `done` and `completed_at` | `toggle_task()` in web.py |
| Color auto-assigned from `LIST_COLORS` palette cycling by list count | `next_color()` in db.py |
| Default `list_id` for MCP `add_task` is 3 (Tasks list) | mcp_server.py |
| Dark mode preference persisted to `localStorage`; applied via `body.dark` CSS class on load | `applyDark()` in static/index.html |
| Default task order: starred → priority → due_date ASC (nulls last) → created_at ASC | `get_tasks()` in web.py, `list_tasks` in mcp_server.py |
| `sort=due_date` order: due_date ASC (nulls last) → starred → priority → created_at ASC | `get_tasks()` in web.py, `list_tasks` in mcp_server.py |

## File Map

```
toodoo/
├── web.py                  # FastAPI app + REST routes
├── db.py                   # SQLite shared layer
├── mcp_server.py           # MCP stdio server
├── static/
│   └── index.html          # SPA frontend
├── tests/
│   ├── conftest.py         # pytest fixtures (tmp_db, client, fresh_db)
│   ├── test_db.py          # db.py unit tests
│   ├── test_web.py         # REST API integration tests
│   └── test_missed_cycles.py  # recurrence logic parametrized tests
├── docs/
│   ├── api.md              # REST API reference
│   ├── architecture.md     # Architecture overview + diagrams
│   ├── data-model.md       # Schema + ER diagram
│   ├── mcp-tools.md        # MCP tools reference
│   └── knowledge-graph.md  # This file
├── mcp-manager-entry.json  # MCP registration config
├── requirements.txt
└── todo.db                 # Runtime database (gitignored)
```
