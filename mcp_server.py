"""
Todo App — MCP stdio server.
The MCP manager spawns this process. Claude connects through the manager.

Run directly (for testing):
    echo '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"0"}}}' | python mcp_server.py
"""

import asyncio
import json
import logging
import sys
from datetime import date
from pathlib import Path

# ensure db.py is importable from the same directory
sys.path.insert(0, str(Path(__file__).parent))

import mcp.types as types
from mcp.server import Server
from mcp.server.stdio import stdio_server

import db

# log to stderr so stdout stays clean for the MCP wire protocol
logging.basicConfig(
    stream=sys.stderr,
    level=logging.INFO,
    format="%(asctime)s [todo-mcp] %(levelname)s %(message)s",
)
log = logging.getLogger("todo-mcp")

# ---------------------------------------------------------------------------
# Server init
# ---------------------------------------------------------------------------

db.init_db()
server = Server("todo-mcp")

# ---------------------------------------------------------------------------
# Tool definitions
# ---------------------------------------------------------------------------

@server.list_tools()
async def list_tools() -> list[types.Tool]:
    log.info("tools/list requested")
    return [
        types.Tool(
            name="list_lists",
            description="Return all task lists with their pending task counts.",
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
        types.Tool(
            name="create_list",
            description="Create a new task list.",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "List name"},
                    "icon": {"type": "string", "description": "Emoji icon, e.g. 🏠"},
                },
                "required": ["name"],
            },
        ),
        types.Tool(
            name="list_tasks",
            description="Return tasks from a list, or all tasks if no list_id given.",
            inputSchema={
                "type": "object",
                "properties": {
                    "list_id":      {"type": "integer", "description": "Filter by list id"},
                    "include_done": {"type": "boolean", "description": "Include completed tasks (default false)"},
                    "sort":         {"type": "string", "enum": ["default", "due_date"],
                                     "description": "Sort order. 'default': starred→priority→due_date(nulls last)→created_at. 'due_date': due_date ASC (nulls last) then default tiebreakers."},
                },
                "required": [],
            },
        ),
        types.Tool(
            name="add_task",
            description="Add a new task to a list.",
            inputSchema={
                "type": "object",
                "properties": {
                    "title":      {"type": "string"},
                    "list_id":    {"type": "integer", "description": "Defaults to 'Tasks' list (id 3)"},
                    "notes":      {"type": "string"},
                    "due_date":   {"type": "string", "description": "Date string: YYYY-MM-DD (date only) or YYYY-MM-DDTHH:MM (with time), e.g. 2025-06-01 or 2025-06-01T09:00"},
                    "priority":   {"type": "string", "enum": ["low", "normal", "high"]},
                    "starred":    {"type": "boolean"},
                    "recurrence": {"type": "string",
                                   "description": "Repeat interval. Use Nd/Nw/Nm/Ny (e.g. '1d', '2w', '3m', '1y') or legacy names daily/weekly/monthly/yearly. Requires due_date."},
                },
                "required": ["title"],
            },
        ),
        types.Tool(
            name="complete_task",
            description=(
                "Mark a task as completed. For recurring tasks this advances the due date "
                "to the next occurrence and logs the completion rather than marking it done."
            ),
            inputSchema={
                "type": "object",
                "properties": {"id": {"type": "integer"}},
                "required": ["id"],
            },
        ),
        types.Tool(
            name="delete_task",
            description="Permanently delete a task.",
            inputSchema={
                "type": "object",
                "properties": {"id": {"type": "integer"}},
                "required": ["id"],
            },
        ),
        types.Tool(
            name="update_task",
            description="Update fields on an existing task.",
            inputSchema={
                "type": "object",
                "properties": {
                    "id":         {"type": "integer"},
                    "title":      {"type": "string"},
                    "notes":      {"type": "string"},
                    "due_date":   {"type": "string", "description": "Date string: YYYY-MM-DD (date only) or YYYY-MM-DDTHH:MM (with time), e.g. 2025-06-01 or 2025-06-01T09:00"},
                    "priority":   {"type": "string", "enum": ["low", "normal", "high"]},
                    "starred":    {"type": "boolean"},
                    "recurrence": {"type": "string", "description": "Nd/Nw/Nm/Ny or daily/weekly/monthly/yearly"},
                },
                "required": ["id"],
            },
        ),
        types.Tool(
            name="list_log",
            description="Return the activity log of completed tasks, newest first.",
            inputSchema={
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "description": "Max entries to return (default 100)"},
                },
                "required": [],
            },
        ),
        types.Tool(
            name="skip_task",
            description="Skip the current occurrence of a recurring task, advancing its due date to the next cycle. Logs the skip in the activity log.",
            inputSchema={
                "type": "object",
                "properties": {
                    "id":     {"type": "integer", "description": "Task id"},
                    "reason": {"type": "string",  "description": "Optional reason for skipping"},
                },
                "required": ["id"],
            },
        ),
        types.Tool(
            name="export_db",
            description="Export a full JSON snapshot of all lists, tasks, and task_log. Useful for backup or inspection.",
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
    ]


# ---------------------------------------------------------------------------
# Tool handlers
# ---------------------------------------------------------------------------

@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    log.info("tools/call  name=%s  args=%s", name, arguments)
    result = _handle(name, arguments)
    log.info("tools/call  result=%s", str(result)[:200])
    return [types.TextContent(type="text", text=json.dumps(result, default=str))]


_RECURRENCE_ALIASES = {"daily": "1d", "weekly": "1w", "monthly": "1m", "yearly": "1y"}


def _parse_recurrence(recurrence: str) -> tuple[int, str]:
    r = _RECURRENCE_ALIASES.get(recurrence, recurrence)
    return int(r[:-1]), r[-1]


def _recurrence_interval(recurrence: str, advance: int) -> str:
    n, unit = _parse_recurrence(recurrence)
    total = n * advance
    if unit == "d":
        return f"+{total} day"
    if unit == "w":
        return f"+{total * 7} day"
    if unit == "m":
        return f"+{total} month"
    return f"+{total} year"


def _advance_due_date_sql() -> str:
    return (
        "CASE WHEN instr(due_date,'T')>0"
        " THEN strftime('%Y-%m-%dT%H:%M',due_date,?)"
        " ELSE date(due_date,?) END"
    )


def _missed_cycles(due_date_str: str, recurrence: str) -> int:
    due = date.fromisoformat(due_date_str[:10])
    today = date.today()
    if today <= due:
        return 0
    n, unit = _parse_recurrence(recurrence)
    days = (today - due).days
    if unit == "d":
        return days // n
    if unit == "w":
        return days // (n * 7)
    if unit == "m":
        months = (today.year - due.year) * 12 + (today.month - due.month)
        if today.day < due.day:
            months -= 1
        return max(0, months // n)
    if unit == "y":
        years = today.year - due.year
        if (today.month, today.day) < (due.month, due.day):
            years -= 1
        return max(0, years // n)
    return 0


def _advance_count(due_date_str: str, recurrence: str) -> int:
    due = date.fromisoformat(due_date_str[:10])
    today = date.today()
    if today <= due:
        return 1
    n, unit = _parse_recurrence(recurrence)
    days = (today - due).days
    if unit == "d":
        interval = n
        return (days + interval - 1) // interval
    if unit == "w":
        interval = n * 7
        return (days + interval - 1) // interval
    return _missed_cycles(due_date_str, recurrence) + 1


def _handle(name: str, args: dict) -> object:
    conn = db.get_conn()
    try:
        if name == "list_lists":
            rows = conn.execute("SELECT * FROM lists ORDER BY sort_order, id").fetchall()
            out = []
            for r in rows:
                d = db.row_to_dict(r)
                d["pending"] = conn.execute(
                    "SELECT COUNT(*) FROM tasks WHERE list_id=? AND done=0", (d["id"],)
                ).fetchone()[0]
                out.append(d)
            return out

        if name == "create_list":
            count = conn.execute("SELECT COUNT(*) FROM lists").fetchone()[0]
            color = db.LIST_COLORS[count % len(db.LIST_COLORS)]
            cur = conn.execute(
                "INSERT INTO lists (name, icon, color) VALUES (?,?,?)",
                (args["name"], args.get("icon", "📋"), color),
            )
            conn.commit()
            return db.row_to_dict(conn.execute("SELECT * FROM lists WHERE id=?", (cur.lastrowid,)).fetchone())

        if name == "list_tasks":
            q = "SELECT * FROM tasks WHERE 1=1"
            params: list = []
            if "list_id" in args:
                q += " AND list_id=?"
                params.append(args["list_id"])
            if not args.get("include_done", False):
                q += " AND done=0"
            priority_case = "CASE priority WHEN 'high' THEN 0 WHEN 'normal' THEN 1 ELSE 2 END"
            if args.get("sort") == "due_date":
                q += f" ORDER BY due_date IS NULL, due_date ASC, starred DESC, {priority_case}, created_at ASC"
            else:
                q += f" ORDER BY sort_order ASC, starred DESC, {priority_case}, due_date IS NULL, due_date ASC, created_at ASC"
            rows = conn.execute(q, params).fetchall()
            return [db.row_to_dict(r) for r in rows]

        if name == "add_task":
            list_id = args.get("list_id", 3)
            max_order = conn.execute(
                "SELECT COALESCE(MAX(sort_order), -1) FROM tasks WHERE list_id=?", (list_id,)
            ).fetchone()[0]
            cur = conn.execute(
                "INSERT INTO tasks (list_id, title, notes, due_date, priority, starred, recurrence, sort_order)"
                " VALUES (?,?,?,?,?,?,?,?)",
                (list_id, args["title"], args.get("notes"), args.get("due_date"),
                 args.get("priority", "normal"), int(args.get("starred", False)),
                 args.get("recurrence"), max_order + 1),
            )
            conn.commit()
            return db.row_to_dict(conn.execute("SELECT * FROM tasks WHERE id=?", (cur.lastrowid,)).fetchone())

        if name == "complete_task":
            row = conn.execute("SELECT * FROM tasks WHERE id=?", (args["id"],)).fetchone()
            if not row:
                return {"error": "not found"}
            list_row = conn.execute("SELECT name FROM lists WHERE id=?", (row["list_id"],)).fetchone()
            list_name = list_row["name"] if list_row else "Unknown"

            if row["recurrence"]:
                missed = _missed_cycles(row["due_date"], row["recurrence"]) if row["due_date"] else 0
                advance = _advance_count(row["due_date"], row["recurrence"]) if row["due_date"] else 1
                interval = _recurrence_interval(row["recurrence"], advance)
                if row["due_date"]:
                    conn.execute(
                        f"UPDATE tasks SET due_date={_advance_due_date_sql()} WHERE id=?",
                        (interval, interval, args["id"]),
                    )
                conn.execute(
                    "INSERT INTO task_log (task_id, task_title, list_id, list_name, recurrence, due_date, cycles_late)"
                    " VALUES (?,?,?,?,?,?,?)",
                    (args["id"], row["title"], row["list_id"], list_name,
                     row["recurrence"], row["due_date"], missed),
                )
            else:
                conn.execute(
                    "UPDATE tasks SET done=1, completed_at=datetime('now') WHERE id=?", (args["id"],)
                )
                conn.execute(
                    "INSERT INTO task_log (task_id, task_title, list_id, list_name, recurrence, due_date, cycles_late)"
                    " VALUES (?,?,?,?,?,?,?)",
                    (args["id"], row["title"], row["list_id"], list_name, None, row["due_date"], 0),
                )
            conn.commit()
            updated = conn.execute("SELECT * FROM tasks WHERE id=?", (args["id"],)).fetchone()
            return db.row_to_dict(updated)

        if name == "delete_task":
            conn.execute("DELETE FROM tasks WHERE id=?", (args["id"],))
            conn.commit()
            return {"deleted": True, "id": args["id"]}

        if name == "update_task":
            fields = {k: v for k, v in args.items() if k != "id"}
            if "starred" in fields:
                fields["starred"] = int(fields["starred"])
            if fields:
                set_clause = ", ".join(f"{k}=?" for k in fields)
                conn.execute(
                    f"UPDATE tasks SET {set_clause} WHERE id=?",
                    (*fields.values(), args["id"]),
                )
                conn.commit()
            row = conn.execute("SELECT * FROM tasks WHERE id=?", (args["id"],)).fetchone()
            return db.row_to_dict(row) if row else {"error": "not found"}

        if name == "list_log":
            rows = conn.execute(
                "SELECT * FROM task_log ORDER BY completed_at DESC LIMIT ?",
                (args.get("limit", 100),),
            ).fetchall()
            return [db.row_to_dict(r) for r in rows]

        if name == "skip_task":
            row = conn.execute("SELECT * FROM tasks WHERE id=?", (args["id"],)).fetchone()
            if not row:
                return {"error": "not found"}
            if not row["recurrence"]:
                return {"error": "Task is not recurring"}
            list_row = conn.execute("SELECT name FROM lists WHERE id=?", (row["list_id"],)).fetchone()
            list_name = list_row["name"] if list_row else "Unknown"
            missed = _missed_cycles(row["due_date"], row["recurrence"]) if row["due_date"] else 0
            advance = _advance_count(row["due_date"], row["recurrence"]) if row["due_date"] else 1
            interval = _recurrence_interval(row["recurrence"], advance)
            if row["due_date"]:
                conn.execute(
                    f"UPDATE tasks SET due_date={_advance_due_date_sql()} WHERE id=?",
                    (interval, interval, args["id"]),
                )
            conn.execute(
                "INSERT INTO task_log (task_id, task_title, list_id, list_name, recurrence, due_date, cycles_late, skipped, reason)"
                " VALUES (?,?,?,?,?,?,?,1,?)",
                (args["id"], row["title"], row["list_id"], list_name,
                 row["recurrence"], row["due_date"], missed, args.get("reason")),
            )
            conn.commit()
            return db.row_to_dict(conn.execute("SELECT * FROM tasks WHERE id=?", (args["id"],)).fetchone())

        if name == "export_db":
            row = conn.execute("SELECT id FROM users ORDER BY id LIMIT 1").fetchone()
            if not row:
                return {"error": "No users found"}
            return db.export_data(conn, row["id"])

        return {"error": f"Unknown tool: {name}"}

    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

async def main():
    log.info("todo-mcp starting up (db=%s)", db.DB_PATH)
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )

if __name__ == "__main__":
    asyncio.run(main())
