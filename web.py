"""
Todo App — web server.
Serves the REST API and the static UI.

Run:  uvicorn web:app --port 8001 --reload
"""

import json
import secrets as _secrets
import sqlite3
from contextlib import asynccontextmanager
from datetime import date
from pathlib import Path

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from pydantic import BaseModel
from starlette.middleware.sessions import SessionMiddleware

import db

# Init DB at import time so the session key is ready before middleware is registered.
db.init_db()
_sess_key = db.get_session_secret()

# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(_app: FastAPI):
    db.init_db()
    yield


app = FastAPI(title="Toodoo", version="0.1.0", lifespan=lifespan)


# auth_middleware must be registered before SessionMiddleware so that
# Starlette's reversed build order places SessionMiddleware outermost (runs first).
@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    path = request.url.path
    if path in ("/login", "/logout", "/register") or path == "/api/health":
        return await call_next(request)
    if not request.session.get("user_id"):
        if path.startswith("/api/"):
            return JSONResponse({"detail": "Unauthorized"}, status_code=401)
        return RedirectResponse("/login")
    return await call_next(request)


app.add_middleware(
    SessionMiddleware,
    secret_key=_sess_key,
    max_age=30 * 24 * 3600,
    https_only=False,
)


# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------


def _uid(request: Request) -> int:
    uid = request.session.get("user_id")
    if not uid:
        raise HTTPException(401, "Not authenticated")
    return uid


def _own_list(conn: sqlite3.Connection, list_id: int, user_id: int) -> sqlite3.Row:
    """Requires the user to be the owner — for destructive/management operations."""
    row = conn.execute(
        "SELECT * FROM lists WHERE id=? AND user_id=?", (list_id, user_id)
    ).fetchone()
    if not row:
        raise HTTPException(404, "List not found")
    return row


def _member_list(conn: sqlite3.Connection, list_id: int, user_id: int) -> sqlite3.Row:
    """Allows any list member (owner or shared) — for task operations."""
    row = conn.execute(
        "SELECT l.* FROM lists l"
        " JOIN list_members lm ON lm.list_id = l.id"
        " WHERE l.id=? AND lm.user_id=?",
        (list_id, user_id),
    ).fetchone()
    if not row:
        raise HTTPException(404, "List not found")
    return row


def _own_task(conn: sqlite3.Connection, task_id: int, user_id: int) -> sqlite3.Row:
    row = conn.execute(
        "SELECT t.* FROM tasks t"
        " JOIN lists l ON t.list_id = l.id"
        " JOIN list_members lm ON lm.list_id = l.id"
        " WHERE t.id=? AND lm.user_id=?",
        (task_id, user_id),
    ).fetchone()
    if not row:
        raise HTTPException(404, "Task not found")
    return row


def _valid_invite(conn: sqlite3.Connection, tok: str) -> bool:
    return bool(conn.execute(
        "SELECT token FROM invites WHERE token=? AND used_at IS NULL"
        " AND datetime(created_at, '+7 days') > datetime('now')",
        (tok,),
    ).fetchone())


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class ListCreate(BaseModel):
    name: str
    icon: str = "📋"
    color: str | None = None


class TaskCreate(BaseModel):
    title: str
    notes: str | None = None
    due_date: str | None = None
    priority: str = "normal"
    starred: bool = False
    recurrence: str | None = None


class TaskPatch(BaseModel):
    title: str | None = None
    notes: str | None = None
    due_date: str | None = None
    priority: str | None = None
    starred: bool | None = None
    recurrence: str | None = None
    list_id: int | None = None


class ImportPayload(BaseModel):
    version: int
    lists: list[dict]
    tasks: list[dict]
    task_log: list[dict]


class SkipBody(BaseModel):
    reason: str | None = None


class MemberAdd(BaseModel):
    username: str


class ReorderBody(BaseModel):
    ids: list[int]


class CategoryCreate(BaseModel):
    name: str


class CategoryPatch(BaseModel):
    name: str | None = None


class ListPatch(BaseModel):
    category_id: int | None = None
    name: str | None = None
    icon: str | None = None


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------


@app.get("/api/health")
def health():
    return {"status": "ok", "auth": True}


# ---------------------------------------------------------------------------
# Auth routes
# ---------------------------------------------------------------------------


@app.get("/api/me")
def get_me(request: Request):
    uid = _uid(request)
    with db.get_conn() as conn:
        row = conn.execute(
            "SELECT id, username, is_admin, created_at FROM users WHERE id=?", (uid,)
        ).fetchone()
    if not row:
        raise HTTPException(404)
    return db.row_to_dict(row)


@app.post("/api/invite")
async def create_invite(request: Request):
    uid = _uid(request)
    with db.get_conn() as conn:
        user = conn.execute("SELECT is_admin FROM users WHERE id=?", (uid,)).fetchone()
        if not user or not user["is_admin"]:
            raise HTTPException(403, "Only admins can create invite links")
        tok = _secrets.token_hex(16)
        conn.execute(
            "INSERT INTO invites (token, created_by) VALUES (?,?)", (tok, uid)
        )
        conn.commit()
    base = str(request.base_url).rstrip("/")
    return {"url": f"{base}/register?token={tok}"}


# ---------------------------------------------------------------------------
# List routes
# ---------------------------------------------------------------------------


@app.get("/api/lists")
def get_lists(request: Request):
    uid = _uid(request)
    with db.get_conn() as conn:
        rows = conn.execute(
            "SELECT l.*, u.username AS owner_username FROM lists l"
            " JOIN list_members lm ON lm.list_id = l.id"
            " JOIN users u ON u.id = l.user_id"
            " WHERE lm.user_id=?"
            " ORDER BY (l.user_id != ?) ASC, l.sort_order ASC, l.id ASC",
            (uid, uid),
        ).fetchall()
        result = []
        for row in rows:
            d = db.row_to_dict(row)
            d["pending"] = conn.execute(
                "SELECT COUNT(*) FROM tasks WHERE list_id=? AND done=0", (d["id"],)
            ).fetchone()[0]
            result.append(d)
        return result


@app.post("/api/lists", status_code=201)
def create_list(request: Request, body: ListCreate):
    uid = _uid(request)
    with db.get_conn() as conn:
        color = body.color or db.next_color(conn, uid)
        cur = conn.execute(
            "INSERT INTO lists (name, icon, color, user_id) VALUES (?,?,?,?)",
            (body.name, body.icon, color, uid),
        )
        new_id = cur.lastrowid
        conn.execute(
            "INSERT INTO list_members (list_id, user_id) VALUES (?,?)", (new_id, uid)
        )
        conn.commit()
        row = conn.execute("SELECT * FROM lists WHERE id=?", (new_id,)).fetchone()
        d = db.row_to_dict(row)
        d["owner_username"] = request.session.get("username", "")
        return d


@app.delete("/api/lists/{list_id}", status_code=204)
def delete_list(request: Request, list_id: int):
    uid = _uid(request)
    with db.get_conn() as conn:
        _own_list(conn, list_id, uid)
        conn.execute("DELETE FROM lists WHERE id=?", (list_id,))
        conn.commit()


@app.get("/api/lists/{list_id}/members")
def get_list_members(request: Request, list_id: int):
    uid = _uid(request)
    with db.get_conn() as conn:
        _own_list(conn, list_id, uid)
        rows = conn.execute(
            "SELECT u.id, u.username FROM users u"
            " JOIN list_members lm ON lm.user_id = u.id"
            " WHERE lm.list_id=? ORDER BY u.username",
            (list_id,),
        ).fetchall()
        return [db.row_to_dict(r) for r in rows]


@app.post("/api/lists/{list_id}/members", status_code=201)
def add_list_member(request: Request, list_id: int, body: MemberAdd):
    uid = _uid(request)
    with db.get_conn() as conn:
        _own_list(conn, list_id, uid)
        target = conn.execute(
            "SELECT id, username FROM users WHERE username=?", (body.username.strip(),)
        ).fetchone()
        if not target:
            raise HTTPException(404, "User not found")
        try:
            conn.execute(
                "INSERT INTO list_members (list_id, user_id) VALUES (?,?)",
                (list_id, target["id"]),
            )
            conn.commit()
        except sqlite3.IntegrityError:
            pass  # already a member
        return {"id": target["id"], "username": target["username"]}


@app.delete("/api/lists/{list_id}/members/{member_uid}", status_code=204)
def remove_list_member(request: Request, list_id: int, member_uid: int):
    uid = _uid(request)
    with db.get_conn() as conn:
        lst = _own_list(conn, list_id, uid)
        if member_uid == lst["user_id"]:
            raise HTTPException(400, "Cannot remove the list owner")
        conn.execute(
            "DELETE FROM list_members WHERE list_id=? AND user_id=?",
            (list_id, member_uid),
        )
        conn.commit()


@app.patch("/api/lists/{list_id}")
def update_list(request: Request, list_id: int, body: ListPatch):
    uid = _uid(request)
    with db.get_conn() as conn:
        _own_list(conn, list_id, uid)
        fields = body.model_dump(exclude_unset=True)
        if not fields:
            return db.row_to_dict(conn.execute("SELECT * FROM lists WHERE id=?", (list_id,)).fetchone())
        if "category_id" in fields and fields["category_id"] is not None:
            if not conn.execute(
                "SELECT id FROM categories WHERE id=? AND user_id=?", (fields["category_id"], uid)
            ).fetchone():
                raise HTTPException(404, "Category not found")
        set_clause = ", ".join(f"{k}=?" for k in fields)
        conn.execute(f"UPDATE lists SET {set_clause} WHERE id=?", (*fields.values(), list_id))
        conn.commit()
        return db.row_to_dict(conn.execute("SELECT * FROM lists WHERE id=?", (list_id,)).fetchone())


@app.post("/api/lists/reorder", status_code=204)
def reorder_lists(request: Request, body: ReorderBody):
    uid = _uid(request)
    with db.get_conn() as conn:
        for i, list_id in enumerate(body.ids):
            conn.execute(
                "UPDATE lists SET sort_order=? WHERE id=? AND user_id=?", (i, list_id, uid)
            )
        conn.commit()


@app.post("/api/lists/{list_id}/tasks/reorder", status_code=204)
def reorder_tasks(request: Request, list_id: int, body: ReorderBody):
    uid = _uid(request)
    with db.get_conn() as conn:
        _member_list(conn, list_id, uid)
        for i, task_id in enumerate(body.ids):
            conn.execute(
                "UPDATE tasks SET sort_order=? WHERE id=? AND list_id=?", (i, task_id, list_id)
            )
        conn.commit()


# ---------------------------------------------------------------------------
# Category routes
# ---------------------------------------------------------------------------


@app.get("/api/categories")
def get_categories(request: Request):
    uid = _uid(request)
    with db.get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM categories WHERE user_id=? ORDER BY sort_order, name", (uid,)
        ).fetchall()
        return [db.row_to_dict(r) for r in rows]


@app.post("/api/categories", status_code=201)
def create_category(request: Request, body: CategoryCreate):
    uid = _uid(request)
    with db.get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO categories (name, user_id) VALUES (?,?)", (body.name.strip(), uid)
        )
        conn.commit()
        return db.row_to_dict(conn.execute("SELECT * FROM categories WHERE id=?", (cur.lastrowid,)).fetchone())


@app.patch("/api/categories/{cat_id}")
def update_category(request: Request, cat_id: int, body: CategoryPatch):
    uid = _uid(request)
    with db.get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM categories WHERE id=? AND user_id=?", (cat_id, uid)
        ).fetchone()
        if not row:
            raise HTTPException(404, "Category not found")
        fields = body.model_dump(exclude_unset=True)
        if not fields:
            return db.row_to_dict(row)
        if "name" in fields:
            fields["name"] = fields["name"].strip()
        set_clause = ", ".join(f"{k}=?" for k in fields)
        conn.execute(f"UPDATE categories SET {set_clause} WHERE id=?", (*fields.values(), cat_id))
        conn.commit()
        return db.row_to_dict(conn.execute("SELECT * FROM categories WHERE id=?", (cat_id,)).fetchone())


@app.delete("/api/categories/{cat_id}", status_code=204)
def delete_category(request: Request, cat_id: int):
    uid = _uid(request)
    with db.get_conn() as conn:
        if not conn.execute(
            "SELECT id FROM categories WHERE id=? AND user_id=?", (cat_id, uid)
        ).fetchone():
            raise HTTPException(404, "Category not found")
        conn.execute("UPDATE lists SET category_id=NULL WHERE category_id=?", (cat_id,))
        conn.execute("DELETE FROM categories WHERE id=?", (cat_id,))
        conn.commit()


# ---------------------------------------------------------------------------
# Task routes
# ---------------------------------------------------------------------------


@app.get("/api/lists/{list_id}/tasks")
def get_tasks(request: Request, list_id: int, include_done: bool = False, sort: str = "default"):
    uid = _uid(request)
    with db.get_conn() as conn:
        _member_list(conn, list_id, uid)
        query = "SELECT * FROM tasks WHERE list_id=?"
        params: list = [list_id]
        if not include_done:
            query += " AND done=0"
        if sort == "due_date":
            query += (
                " ORDER BY due_date IS NULL, due_date ASC,"
                " starred DESC, CASE priority WHEN 'high' THEN 0 WHEN 'normal' THEN 1 ELSE 2 END, created_at ASC"
            )
        else:
            query += (
                " ORDER BY sort_order ASC, starred DESC,"
                " CASE priority WHEN 'high' THEN 0 WHEN 'normal' THEN 1 ELSE 2 END,"
                " due_date IS NULL, due_date ASC, created_at ASC"
            )
        rows = conn.execute(query, params).fetchall()
        return [db.row_to_dict(r) for r in rows]


@app.post("/api/lists/{list_id}/tasks", status_code=201)
def add_task(request: Request, list_id: int, body: TaskCreate):
    uid = _uid(request)
    with db.get_conn() as conn:
        _member_list(conn, list_id, uid)
        max_order = conn.execute(
            "SELECT COALESCE(MAX(sort_order), -1) FROM tasks WHERE list_id=?", (list_id,)
        ).fetchone()[0]
        cur = conn.execute(
            "INSERT INTO tasks (list_id, title, notes, due_date, priority, starred, recurrence, sort_order)"
            " VALUES (?,?,?,?,?,?,?,?)",
            (list_id, body.title, body.notes, body.due_date, body.priority,
             int(body.starred), body.recurrence, max_order + 1),
        )
        conn.commit()
        task = conn.execute("SELECT * FROM tasks WHERE id=?", (cur.lastrowid,)).fetchone()
        return db.row_to_dict(task)


@app.patch("/api/tasks/{task_id}")
def update_task(request: Request, task_id: int, body: TaskPatch):
    uid = _uid(request)
    with db.get_conn() as conn:
        row = _own_task(conn, task_id, uid)
        fields = body.model_dump(exclude_unset=True)
        if not fields:
            return db.row_to_dict(row)
        if "list_id" in fields:
            if not conn.execute(
                "SELECT l.id FROM lists l JOIN list_members lm ON lm.list_id=l.id"
                " WHERE l.id=? AND lm.user_id=?",
                (fields["list_id"], uid),
            ).fetchone():
                raise HTTPException(404, "Target list not found")
        if "starred" in fields:
            fields["starred"] = int(fields["starred"])
        set_clause = ", ".join(f"{k}=?" for k in fields)
        conn.execute(
            f"UPDATE tasks SET {set_clause} WHERE id=?",
            (*fields.values(), task_id),
        )
        conn.commit()
        updated = conn.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
        return db.row_to_dict(updated)


_RECURRENCE_ALIASES = {"daily": "1d", "weekly": "1w", "monthly": "1m", "yearly": "1y"}
_RECURRENCE_UNITS = {"d": "day", "w": "week", "m": "month", "y": "year"}


def _parse_recurrence(recurrence: str) -> tuple[int, str]:
    """Return (n, unit) where unit is one of d/w/m/y. Handles legacy aliases."""
    r = _RECURRENCE_ALIASES.get(recurrence, recurrence)
    n = int(r[:-1])
    unit = r[-1]
    return n, unit


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
    """SQL expression that advances due_date by a modifier, preserving HH:MM if present."""
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
    """Cycles to advance from due_date so the new due date lands on today or later.

    For day/week intervals: ceiling division ensures the result is the earliest
    scheduled occurrence on or after today (not always +1 past today).
    For month/year intervals: falls back to missed+1 since calendar months aren't
    fixed-length days.
    """
    due = date.fromisoformat(due_date_str[:10])
    today = date.today()
    if today <= due:
        return 1
    n, unit = _parse_recurrence(recurrence)
    days = (today - due).days
    if unit == "d":
        interval = n
        return (days + interval - 1) // interval  # ceil(days / interval)
    if unit == "w":
        interval = n * 7
        return (days + interval - 1) // interval
    return _missed_cycles(due_date_str, recurrence) + 1


@app.post("/api/tasks/{task_id}/toggle")
def toggle_task(request: Request, task_id: int):
    uid = _uid(request)
    with db.get_conn() as conn:
        row = _own_task(conn, task_id, uid)
        list_row = conn.execute("SELECT name FROM lists WHERE id=?", (row["list_id"],)).fetchone()
        list_name = list_row["name"] if list_row else "Unknown"

        if not row["done"] and row["recurrence"]:
            missed = _missed_cycles(row["due_date"], row["recurrence"]) if row["due_date"] else 0
            advance = _advance_count(row["due_date"], row["recurrence"]) if row["due_date"] else 1
            interval = _recurrence_interval(row["recurrence"], advance)
            if row["due_date"]:
                conn.execute(
                    f"UPDATE tasks SET due_date={_advance_due_date_sql()} WHERE id=?",
                    (interval, interval, task_id),
                )
            conn.execute(
                "INSERT INTO task_log"
                " (task_id, task_title, list_id, list_name, recurrence, due_date, cycles_late, skipped)"
                " VALUES (?,?,?,?,?,?,?,0)",
                (task_id, row["title"], row["list_id"], list_name,
                 row["recurrence"], row["due_date"], missed),
            )
        elif row["done"]:
            conn.execute("UPDATE tasks SET done=0, completed_at=NULL WHERE id=?", (task_id,))
        else:
            conn.execute(
                "UPDATE tasks SET done=1, completed_at=datetime('now') WHERE id=?", (task_id,)
            )
            conn.execute(
                "INSERT INTO task_log"
                " (task_id, task_title, list_id, list_name, recurrence, due_date, cycles_late, skipped)"
                " VALUES (?,?,?,?,?,?,?,0)",
                (task_id, row["title"], row["list_id"], list_name, None, row["due_date"], 0),
            )
        conn.commit()
        updated = conn.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
        return db.row_to_dict(updated)


@app.post("/api/tasks/{task_id}/star")
def star_task(request: Request, task_id: int):
    uid = _uid(request)
    with db.get_conn() as conn:
        row = _own_task(conn, task_id, uid)
        conn.execute(
            "UPDATE tasks SET starred=? WHERE id=?", (0 if row["starred"] else 1, task_id)
        )
        conn.commit()
        updated = conn.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
        return db.row_to_dict(updated)


@app.post("/api/tasks/{task_id}/skip")
def skip_task(request: Request, task_id: int, body: SkipBody):
    uid = _uid(request)
    with db.get_conn() as conn:
        row = _own_task(conn, task_id, uid)
        if not row["recurrence"]:
            raise HTTPException(400, "Task is not recurring")
        list_row = conn.execute("SELECT name FROM lists WHERE id=?", (row["list_id"],)).fetchone()
        list_name = list_row["name"] if list_row else "Unknown"
        missed = _missed_cycles(row["due_date"], row["recurrence"]) if row["due_date"] else 0
        advance = _advance_count(row["due_date"], row["recurrence"]) if row["due_date"] else 1
        interval = _recurrence_interval(row["recurrence"], advance)
        if row["due_date"]:
            conn.execute(
                f"UPDATE tasks SET due_date={_advance_due_date_sql()} WHERE id=?",
                (interval, interval, task_id),
            )
        conn.execute(
            "INSERT INTO task_log"
            " (task_id, task_title, list_id, list_name, recurrence, due_date, cycles_late, skipped, reason)"
            " VALUES (?,?,?,?,?,?,?,1,?)",
            (task_id, row["title"], row["list_id"], list_name,
             row["recurrence"], row["due_date"], missed, body.reason),
        )
        conn.commit()
        updated = conn.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
        return db.row_to_dict(updated)


@app.get("/api/log")
def get_log(request: Request, limit: int = 500):
    uid = _uid(request)
    with db.get_conn() as conn:
        rows = conn.execute(
            "SELECT tl.* FROM task_log tl"
            " WHERE tl.list_id IN (SELECT list_id FROM list_members WHERE user_id=?)"
            " ORDER BY tl.completed_at DESC LIMIT ?",
            (uid, limit),
        ).fetchall()
        return [db.row_to_dict(r) for r in rows]


@app.delete("/api/lists/{list_id}/tasks/completed")
def clear_completed(request: Request, list_id: int):
    uid = _uid(request)
    with db.get_conn() as conn:
        _member_list(conn, list_id, uid)
        result = conn.execute("DELETE FROM tasks WHERE list_id=? AND done=1", (list_id,))
        conn.commit()
        return {"cleared": result.rowcount}


@app.delete("/api/tasks/{task_id}", status_code=204)
def delete_task(request: Request, task_id: int):
    uid = _uid(request)
    with db.get_conn() as conn:
        _own_task(conn, task_id, uid)
        conn.execute("DELETE FROM tasks WHERE id=?", (task_id,))
        conn.commit()


# ---------------------------------------------------------------------------
# Export / Import
# ---------------------------------------------------------------------------


@app.get("/api/export")
def export_db(request: Request):
    uid = _uid(request)
    with db.get_conn() as conn:
        data = db.export_data(conn, uid)
    return Response(
        content=json.dumps(data),
        media_type="application/json",
        headers={"Content-Disposition": "attachment; filename=toodoo-backup.json"},
    )


@app.post("/api/import")
def import_db(request: Request, body: ImportPayload):
    if body.version != 1:
        raise HTTPException(422, f"Unsupported export version: {body.version}")
    uid = _uid(request)
    with db.get_conn() as conn:
        # Delete only this user's data
        old_ids = [r[0] for r in conn.execute(
            "SELECT id FROM lists WHERE user_id=?", (uid,)
        ).fetchall()]
        if old_ids:
            ph = ",".join("?" * len(old_ids))
            conn.execute(f"DELETE FROM task_log WHERE list_id IN ({ph})", old_ids)
        conn.execute("DELETE FROM lists WHERE user_id=?", (uid,))

        # Import lists, remapping IDs
        id_map: dict[int, int] = {}
        for row in body.lists:
            data = {k: v for k, v in row.items() if k != "id"}
            data["user_id"] = uid
            cols = ", ".join(data.keys())
            phs = ", ".join("?" * len(data))
            cur = conn.execute(f"INSERT INTO lists ({cols}) VALUES ({phs})", list(data.values()))
            new_id = cur.lastrowid
            assert new_id is not None
            id_map[row["id"]] = new_id
            conn.execute(
                "INSERT INTO list_members (list_id, user_id) VALUES (?,?)", (new_id, uid)
            )

        for row in body.tasks:
            data = {k: v for k, v in row.items() if k != "id"}
            if data.get("list_id") in id_map:
                data["list_id"] = id_map[data["list_id"]]
            cols = ", ".join(data.keys())
            phs = ", ".join("?" * len(data))
            conn.execute(f"INSERT INTO tasks ({cols}) VALUES ({phs})", list(data.values()))

        for row in body.task_log:
            data = {k: v for k, v in row.items() if k != "id"}
            if data.get("list_id") in id_map:
                data["list_id"] = id_map[data["list_id"]]
            cols = ", ".join(data.keys())
            phs = ", ".join("?" * len(data))
            conn.execute(f"INSERT INTO task_log ({cols}) VALUES ({phs})", list(data.values()))

        conn.commit()
    return {"imported": {
        "lists": len(body.lists),
        "tasks": len(body.tasks),
        "task_log": len(body.task_log),
    }}


# ---------------------------------------------------------------------------
# UI
# ---------------------------------------------------------------------------

_static = Path(__file__).parent / "static"


@app.get("/", response_class=HTMLResponse)
def serve_ui():
    return HTMLResponse((_static / "index.html").read_text(encoding="utf-8"))


@app.get("/login", response_class=HTMLResponse)
def login_page():
    return HTMLResponse((_static / "login.html").read_text(encoding="utf-8"))


@app.post("/login")
async def login_submit(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
):
    with db.get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE username=?", (username.strip(),)
        ).fetchone()
    if row and db.verify_pw(password, row["pw_hash"]):
        request.session["user_id"] = row["id"]
        request.session["username"] = row["username"]
        return RedirectResponse("/", status_code=303)
    return RedirectResponse("/login?error=1", status_code=303)


@app.get("/register", response_class=HTMLResponse)
def register_page(token: str = ""):
    with db.get_conn() as conn:
        if db.user_count(conn) == 0:
            return HTMLResponse((_static / "register.html").read_text(encoding="utf-8"))
        if token and _valid_invite(conn, token):
            return HTMLResponse((_static / "register.html").read_text(encoding="utf-8"))
    return RedirectResponse("/login?error=invite", status_code=303)


@app.post("/register")
async def register_submit(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    token: str = Form(""),
):
    username = username.strip()
    if not (1 <= len(username) <= 50):
        redir = f"/register?error=username&token={token}" if token else "/register?error=username"
        return RedirectResponse(redir, status_code=303)

    with db.get_conn() as conn:
        count = db.user_count(conn)
        if count > 0:
            if not token or not _valid_invite(conn, token):
                return RedirectResponse("/login?error=invite", status_code=303)

        if conn.execute("SELECT id FROM users WHERE username=?", (username,)).fetchone():
            redir = f"/register?error=taken&token={token}" if token else "/register?error=taken"
            return RedirectResponse(redir, status_code=303)

        is_admin = 1 if count == 0 else 0
        cur = conn.execute(
            "INSERT INTO users (username, pw_hash, is_admin) VALUES (?,?,?)",
            (username, db.hash_pw(password), is_admin),
        )
        new_uid = cur.lastrowid
        assert new_uid is not None

        if token:
            conn.execute(
                "UPDATE invites SET used_at=datetime('now'), used_by=? WHERE token=?",
                (new_uid, token),
            )

        # Claim orphaned lists (upgrade from single-password mode) or seed defaults
        result = conn.execute(
            "UPDATE lists SET user_id=? WHERE user_id IS NULL", (new_uid,)
        )
        if result.rowcount == 0:
            db.seed_for_user(conn, new_uid)
        else:
            # Backfill list_members for newly claimed lists
            conn.execute("""
                INSERT OR IGNORE INTO list_members (list_id, user_id)
                SELECT id, user_id FROM lists WHERE user_id=?
            """, (new_uid,))

        conn.commit()

    request.session["user_id"] = new_uid
    request.session["username"] = username
    return RedirectResponse("/", status_code=303)


@app.post("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login", status_code=303)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8001)
