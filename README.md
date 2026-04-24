# Toodoo

A self-hosted personal todo app with multi-user support, shared lists, and a Claude MCP integration. Built with FastAPI and SQLite — single binary, no external services required.

## Features

- **Multiple users** — invite-based registration; each user has private lists by default
- **Shared lists** — owners can share any list with other users
- **Task management** — priorities, due dates, starred tasks, recurring tasks, notes
- **Activity log** — history of completed and skipped recurring tasks
- **Dark mode** — follows system preference
- **Mobile-friendly** — responsive layout with collapsible sidebar
- **MCP server** — lets Claude manage your todos directly via the Model Context Protocol
- **No external services** — SQLite database, no email, no cloud dependencies

## Quick Start (Docker)

```bash
curl -O https://raw.githubusercontent.com/daggerplusplus/toodoo/main/docker-compose.yml
docker compose up -d
```

Open http://localhost:8001 and create the first account — that account becomes the admin and can invite other users.

To update to the latest version:

```bash
docker compose pull && docker compose up -d
```

## Configuration

All configuration is via environment variables. Edit `docker-compose.yml` or create a `.env` file alongside it.

| Variable | Default | Description |
|----------|---------|-------------|
| `TODO_DB` | `/data/todo.db` | Path to the SQLite database file |
| `PORT` | `8001` | Port the web server listens on |
| `HOST` | `0.0.0.0` | Host the web server binds to |

The database is stored in a named Docker volume (`toodoo-data`) and persists across restarts and image updates.

## Running Locally (without Docker)

Requires Python 3.12+.

```bash
git clone https://github.com/daggerplusplus/toodoo
cd toodoo
python -m venv venv && source venv/bin/activate
pip install -r requirements-dev.txt
uvicorn web:app --host 0.0.0.0 --port 8001 --reload
```

## User Management

- The **first account** registered is automatically the admin
- Admins can generate invite links from the sidebar ("Invite someone")
- Invited users register via the link and get their own private lists
- Any user can share their lists with other users from the list header

## MCP Integration

Toodoo includes an MCP server that lets Claude read and manage your todos. To use it, configure your MCP client with `mcp-manager-entry.json` (update the `cwd` and `TODO_DB` paths for your environment):

```json
{
  "name": "toodoo",
  "command": "python",
  "args": ["mcp_server.py"],
  "cwd": "/path/to/toodoo",
  "env": {
    "TODO_DB": "/path/to/toodoo/todo.db"
  }
}
```

Available tools: `list_lists`, `create_list`, `list_tasks`, `add_task`, `complete_task`, `update_task`, `delete_task`.

## Tech Stack

- **Backend**: [FastAPI](https://fastapi.tiangolo.com/) + [uvicorn](https://www.uvicorn.org/)
- **Database**: SQLite (WAL mode) via the standard library
- **Frontend**: Vanilla JS SPA — no framework, no build step
- **Auth**: Session cookies via [itsdangerous](https://itsdangerous.palletsprojects.com/), passwords hashed with `hashlib.scrypt`
- **MCP**: [Model Context Protocol](https://modelcontextprotocol.io/) stdio server

## API

The REST API is available at `/api/*`. All endpoints require authentication.

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/health` | Health check (no auth required) |
| `GET` | `/api/me` | Current user info |
| `GET/POST` | `/api/lists` | List all lists / create a list |
| `DELETE` | `/api/lists/{id}` | Delete a list (owner only) |
| `GET/POST` | `/api/lists/{id}/members` | List members / add member by username |
| `DELETE` | `/api/lists/{id}/members/{uid}` | Remove a member |
| `GET/POST` | `/api/lists/{id}/tasks` | List tasks / add a task |
| `PATCH/DELETE` | `/api/tasks/{id}` | Update / delete a task |
| `POST` | `/api/tasks/{id}/toggle` | Toggle completion |
| `POST` | `/api/tasks/{id}/star` | Toggle starred |
| `GET` | `/api/log` | Activity log |
| `GET/POST` | `/api/export` `/api/import` | Backup and restore |
| `POST` | `/api/invite` | Generate invite link (admin only) |

## License

MIT
