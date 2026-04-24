# Architecture

## Overview

A personal to-do app with two entry points sharing one SQLite database.

```
┌─────────────────────────────────────────────┐
│                   Clients                    │
│  Browser (SPA)          Claude / MCP client  │
└────────┬────────────────────────┬────────────┘
         │ HTTP                   │ JSON-RPC (stdio)
         ▼                        ▼
┌─────────────────┐    ┌──────────────────────┐
│    web.py       │    │    mcp_server.py      │
│  FastAPI app    │    │   MCP stdio server    │
│  port 8001      │    │                       │
└────────┬────────┘    └──────────┬────────────┘
         │                        │
         └──────────┬─────────────┘
                    ▼
           ┌────────────────┐
           │     db.py      │
           │  get_conn()    │
           │  init_db()     │
           │  row_to_dict() │
           │  next_color()  │
           └───────┬────────┘
                   │ sqlite3 (WAL mode)
                   ▼
           ┌────────────────┐
           │   todo.db      │
           │  lists         │
           │  tasks         │
           │  task_log      │
           └────────────────┘
```

## Entry Points

### web.py
FastAPI application serving:
- REST API at `/api/*`
- Static SPA at `/` (serves `static/index.html`)

All business logic is raw SQL — no ORM. Each route opens a connection via `db.get_conn()` and closes it on exit (context manager).

### mcp_server.py
MCP stdio server that exposes the todo data to Claude as tools. Communicates via JSON-RPC over stdin/stdout. Logs to stderr to keep the wire protocol clean.

**Tools exposed:** `list_lists`, `create_list`, `list_tasks`, `add_task`, `complete_task`, `update_task`, `delete_task`

## Shared Layer (db.py)

- `get_conn()` — opens WAL-mode SQLite with foreign keys enabled
- `init_db()` — idempotent schema creation + default list seeding
- `next_color()` — cycles through `LIST_COLORS` palette for new lists
- `row_to_dict()` — converts `sqlite3.Row` to plain dict

DB path defaults to `todo.db` beside the script; override via `TODO_DB` env var.

## Frontend (static/index.html)

Self-contained SPA — vanilla JS, no framework, no build step. All state lives in module-level variables. `renderSidebar()` and `renderTasks()` perform full re-renders on every state change.

Dark mode is toggled via a moon/sun button in the sidebar header. The `body.dark` class overrides CSS custom properties; preference is persisted to `localStorage`.

## Recurrence Logic

When a recurring task is toggled done:
1. `_missed_cycles()` computes how many periods have passed since `due_date`
2. `due_date` is advanced by `(missed + 1)` cycles using SQLite's `date()` function
3. A row is written to `task_log` (task stays `done=0`)

Supported periods: `daily`, `weekly`, `monthly`, `yearly`.

## Deployment

```bash
uvicorn web:app --host 0.0.0.0 --port 8001 --reload
```

`--host 0.0.0.0` required for access outside the container (e.g. Tailscale).

MCP registration: `mcp-manager-entry.json` (update `cwd` and `TODO_DB` before deploying).
