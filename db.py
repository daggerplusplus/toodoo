"""
Shared SQLite database layer.
Both web.py and mcp_server.py import this — WAL mode handles concurrent access.
"""

import hashlib
import hmac
import os
import secrets
import sqlite3
from pathlib import Path

DB_PATH = os.getenv("TODO_DB", str(Path(__file__).parent / "todo.db"))

LIST_COLORS = ["#3b82f6", "#f43f5e", "#8b5cf6", "#10b981",
               "#f59e0b", "#06b6d4", "#ec4899", "#84cc16"]


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db() -> None:
    with get_conn() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            username   TEXT    NOT NULL UNIQUE,
            pw_hash    TEXT    NOT NULL,
            is_admin   INTEGER NOT NULL DEFAULT 0,
            created_at TEXT    NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS invites (
            token      TEXT    PRIMARY KEY,
            created_by INTEGER NOT NULL REFERENCES users(id),
            created_at TEXT    NOT NULL DEFAULT (datetime('now')),
            used_at    TEXT,
            used_by    INTEGER REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS lists (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            name       TEXT    NOT NULL,
            icon       TEXT    NOT NULL DEFAULT '📋',
            color      TEXT    NOT NULL DEFAULT '#3b82f6',
            created_at TEXT    NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS tasks (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            list_id      INTEGER NOT NULL REFERENCES lists(id) ON DELETE CASCADE,
            title        TEXT    NOT NULL,
            notes        TEXT,
            due_date     TEXT,
            priority     TEXT    NOT NULL DEFAULT 'normal',
            done         INTEGER NOT NULL DEFAULT 0,
            starred      INTEGER NOT NULL DEFAULT 0,
            created_at   TEXT    NOT NULL DEFAULT (datetime('now')),
            completed_at TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_tasks_list ON tasks(list_id);
        CREATE INDEX IF NOT EXISTS idx_tasks_done  ON tasks(done);

        CREATE TABLE IF NOT EXISTS task_log (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id      INTEGER,
            task_title   TEXT    NOT NULL,
            list_id      INTEGER,
            list_name    TEXT    NOT NULL,
            recurrence   TEXT,
            due_date     TEXT,
            cycles_late  INTEGER NOT NULL DEFAULT 0,
            completed_at TEXT    NOT NULL DEFAULT (datetime('now'))
        );

        CREATE INDEX IF NOT EXISTS idx_log_completed ON task_log(completed_at);
        CREATE INDEX IF NOT EXISTS idx_log_task      ON task_log(task_id);

        CREATE TABLE IF NOT EXISTS list_members (
            list_id INTEGER NOT NULL REFERENCES lists(id) ON DELETE CASCADE,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            PRIMARY KEY (list_id, user_id)
        );

        CREATE TABLE IF NOT EXISTS settings (
            key   TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
        """)

        # migrations for existing databases
        cols = {r[1] for r in conn.execute("PRAGMA table_info(tasks)")}
        if "recurrence" not in cols:
            conn.execute("ALTER TABLE tasks ADD COLUMN recurrence TEXT")

        log_cols = {r[1] for r in conn.execute("PRAGMA table_info(task_log)")}
        if "skipped" not in log_cols:
            conn.execute("ALTER TABLE task_log ADD COLUMN skipped INTEGER NOT NULL DEFAULT 0")
        if "reason" not in log_cols:
            conn.execute("ALTER TABLE task_log ADD COLUMN reason TEXT")

        list_cols = {r[1] for r in conn.execute("PRAGMA table_info(lists)")}
        if "user_id" not in list_cols:
            conn.execute("ALTER TABLE lists ADD COLUMN user_id INTEGER REFERENCES users(id)")

        user_cols = {r[1] for r in conn.execute("PRAGMA table_info(users)")}
        if "is_admin" not in user_cols:
            conn.execute("ALTER TABLE users ADD COLUMN is_admin INTEGER NOT NULL DEFAULT 0")
            conn.execute(
                "UPDATE users SET is_admin=1 WHERE id=(SELECT MIN(id) FROM users)"
            )

        # Backfill list_members from lists.user_id for existing databases
        if conn.execute("SELECT COUNT(*) FROM list_members").fetchone()[0] == 0:
            conn.execute("""
                INSERT OR IGNORE INTO list_members (list_id, user_id)
                SELECT id, user_id FROM lists WHERE user_id IS NOT NULL
            """)


def get_session_secret() -> str:
    with get_conn() as conn:
        row = conn.execute("SELECT value FROM settings WHERE key='session_secret'").fetchone()
        if row:
            return row["value"]
        val = secrets.token_hex(32)
        conn.execute("INSERT INTO settings (key, value) VALUES ('session_secret', ?)", (val,))
        conn.commit()
        return val


def user_count(conn: sqlite3.Connection) -> int:
    return conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]


def hash_pw(pw: str) -> str:
    salt = os.urandom(16)
    key = hashlib.scrypt(pw.encode(), salt=salt, n=16384, r=8, p=1, dklen=32)
    return salt.hex() + ":" + key.hex()


def verify_pw(pw: str, stored: str) -> bool:
    try:
        salt_hex, key_hex = stored.split(":", 1)
        key = hashlib.scrypt(pw.encode(), salt=bytes.fromhex(salt_hex), n=16384, r=8, p=1, dklen=32)
        return hmac.compare_digest(key.hex(), key_hex)
    except Exception:
        return False


def seed_for_user(conn: sqlite3.Connection, user_id: int) -> None:
    for name, icon, color in [
        ("My Day",    "☀️",  "#0ea5e9"),
        ("Important", "⭐",  "#f43f5e"),
        ("Tasks",     "📋",  "#6366f1"),
    ]:
        cur = conn.execute(
            "INSERT INTO lists (name, icon, color, user_id) VALUES (?,?,?,?)",
            (name, icon, color, user_id),
        )
        conn.execute(
            "INSERT INTO list_members (list_id, user_id) VALUES (?,?)",
            (cur.lastrowid, user_id),
        )


def row_to_dict(row: sqlite3.Row) -> dict:
    return dict(row)


def next_color(conn: sqlite3.Connection, user_id: int) -> str:
    count = conn.execute("SELECT COUNT(*) FROM lists WHERE user_id=?", (user_id,)).fetchone()[0]
    return LIST_COLORS[count % len(LIST_COLORS)]


def export_data(conn: sqlite3.Connection, user_id: int) -> dict:
    from datetime import datetime, timezone
    lists = [row_to_dict(r) for r in conn.execute(
        "SELECT * FROM lists WHERE user_id=? ORDER BY id", (user_id,)
    ).fetchall()]
    list_ids = tuple(lst["id"] for lst in lists)
    if list_ids:
        ph = ",".join("?" * len(list_ids))
        tasks = [row_to_dict(r) for r in conn.execute(
            f"SELECT * FROM tasks WHERE list_id IN ({ph}) ORDER BY id", list_ids
        ).fetchall()]
        logs = [row_to_dict(r) for r in conn.execute(
            f"SELECT * FROM task_log WHERE list_id IN ({ph}) ORDER BY id", list_ids
        ).fetchall()]
    else:
        tasks, logs = [], []
    return {
        "version": 1,
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "lists": lists,
        "tasks": tasks,
        "task_log": logs,
    }
