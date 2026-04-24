# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

This app is a personal clone of Microsoft To-Do with custom adjustments.

## Commands

```bash
# Install dependencies (venv already present)
source venv/bin/activate
pip install -r requirements.txt

# Run the web server (default port 8001)
# --host 0.0.0.0 is required to be reachable outside the container (e.g. via Tailscale)
uvicorn web:app --host 0.0.0.0 --port 8001 --reload

# Run the MCP server directly (for testing — sends JSON-RPC over stdio)
echo '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"0"}}}' | python mcp_server.py

# Override the DB path
TODO_DB=/path/to/other.db uvicorn web:app --host 0.0.0.0 --port 8001
```

There is no test suite or linter configured.

## Architecture

The app has two entry points that share a single SQLite database via `db.py`:

- **`web.py`** — FastAPI REST API + serves `static/index.html`. All business logic is raw SQL (no ORM). Routes follow the pattern `GET/POST /api/lists`, `GET/POST /api/lists/{id}/tasks`, `PATCH/DELETE /api/tasks/{id}`, plus `/api/tasks/{id}/toggle` and `/api/tasks/{id}/star`.
- **`mcp_server.py`** — MCP stdio server exposing `list_lists`, `create_list`, `list_tasks`, `add_task`, `complete_task`, `update_task`, `delete_task` tools. Allows Claude to manage todos directly. Logs to stderr to keep stdout clean for the MCP wire protocol.
- **`db.py`** — Shared layer: `get_conn()` opens a WAL-mode SQLite connection with foreign keys enabled. `init_db()` creates the schema and seeds three default lists. DB path defaults to `todo.db` beside the script, overridable via `TODO_DB` env var.
- **`static/index.html`** — Self-contained single-page app (vanilla JS, no framework). All state is in module-level variables; `renderSidebar()` and `renderTasks()` do full re-renders on every change.

### Data model

```
lists  (id, name, icon, color, created_at)
tasks  (id, list_id→lists.id CASCADE, title, notes, due_date, priority, done, starred, created_at, completed_at)
```

Task ordering in queries: starred first, then `high → normal → low` priority, then `created_at ASC`.

### MCP integration

`mcp-manager-entry.json` is a registration file for an MCP manager. Update `cwd` and `TODO_DB` paths before deploying. The `add_task` tool defaults `list_id` to `3` (the seeded "Tasks" list).
