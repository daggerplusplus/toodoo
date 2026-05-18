# Toodoo

A self-hosted personal todo app with multi-user support, shared lists, and a Claude MCP integration. Built with FastAPI and SQLite — single binary, no external services required.

## Features

- **Multiple users** — invite-based registration; each user has private lists by default
- **Shared lists** — owners can share any list with other users
- **Task management** — priorities, due dates (with optional time of day), starred tasks, recurring tasks, notes
- **Activity log** — history of completed and skipped recurring tasks
- **Dark mode** — follows system preference
- **Mobile-friendly** — responsive layout with collapsible sidebar
- **MCP server** — lets Claude manage your todos directly via the Model Context Protocol
- **Electron desktop app** — installable Windows client with persistent auto-login
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

Available tools: `list_lists`, `create_list`, `list_tasks`, `add_task`, `complete_task`, `update_task`, `delete_task`, `skip_task`, `list_log`, `export_db`.

## Electron Desktop App

A lightweight, installable Windows desktop client that connects to your Toodoo server. The Electron app is a **thin client** — it does not run its own backend, it loads the web UI from your server in a native window.

### Prerequisites

- A running Toodoo server (Docker or local)
- Node.js 18+ installed locally (for building/installing the desktop app)

### Setup

```bash
cd electron          # or wherever the electron folder lives
npm install
```

### Running

```bash
npm start
```

On first launch, you'll be prompted to enter the URL of your Toodoo server. The app connects to it and loads the same web UI in a native window.

### Auto-login

The app saves your server URL and API token to disk (`%APPDATA%\Toodoo\config.json`). On subsequent launches it verifies the saved token and logs in automatically — no need to enter credentials each time.

### Installing as a Windows App

Build an NSIS installer:

```bash
npm run build
```

This produces a Windows installer in `dist/` that you can run to install Toodoo as a regular app with a Start Menu shortcut and desktop icon.

Configuration: `electron-builder.json` — change `appId`, `productName`, or target platform as needed.

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
| `PATCH` | `/api/lists/{id}` | Update list (category, name, icon) |
| `DELETE` | `/api/lists/{id}` | Delete a list (owner only) |
| `POST` | `/api/lists/reorder` | Reorder lists |
| `GET/POST` | `/api/lists/{id}/members` | List members / add member by username |
| `DELETE` | `/api/lists/{id}/members/{uid}` | Remove a member |
| `GET/POST` | `/api/categories` | List categories / create a category |
| `PATCH/DELETE` | `/api/categories/{id}` | Rename / delete a category |
| `GET/POST` | `/api/lists/{id}/tasks` | List tasks / add a task |
| `POST` | `/api/lists/{id}/tasks/reorder` | Reorder tasks |
| `PATCH/DELETE` | `/api/tasks/{id}` | Update / delete a task |
| `POST` | `/api/tasks/{id}/toggle` | Toggle completion |
| `POST` | `/api/tasks/{id}/star` | Toggle starred |
| `POST` | `/api/tasks/{id}/skip` | Skip recurring task occurrence |
| `GET` | `/api/log` | Activity log |
| `GET/POST` | `/api/export` `/api/import` | Backup and restore |
| `POST` | `/api/invite` | Generate invite link (admin only) |

## License

MIT
