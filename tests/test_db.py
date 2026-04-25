import os
import tempfile
import pytest
import db


@pytest.fixture
def fresh_db(tmp_path):
    db_path = str(tmp_path / "test.db")
    original = db.DB_PATH
    db.DB_PATH = db_path
    db.init_db()
    yield db_path
    db.DB_PATH = original


def test_init_db_creates_tables(fresh_db):
    conn = db.get_conn()
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    assert {"lists", "tasks", "task_log"}.issubset(tables)


def _make_user(conn):
    cur = conn.execute(
        "INSERT INTO users (username, pw_hash, is_admin) VALUES (?,?,1)",
        ("u", "hash"),
    )
    conn.commit()
    return cur.lastrowid


def test_init_db_seeds_default_lists(fresh_db):
    conn = db.get_conn()
    uid = _make_user(conn)
    db.seed_for_user(conn, uid)
    conn.commit()
    names = [r[0] for r in conn.execute("SELECT name FROM lists ORDER BY id").fetchall()]
    assert names == ["My Day", "Important", "Tasks"]


def test_init_db_idempotent(fresh_db):
    db.init_db()  # second call must not raise or duplicate
    conn = db.get_conn()
    assert conn.execute("SELECT COUNT(*) FROM lists").fetchone()[0] == 0


def test_next_color_cycles(fresh_db):
    conn = db.get_conn()
    uid = _make_user(conn)
    first = db.next_color(conn, uid)
    assert first in db.LIST_COLORS


def test_row_to_dict(fresh_db):
    conn = db.get_conn()
    conn.execute("INSERT INTO lists (name, icon, color) VALUES ('Test','📋','#000')")
    conn.commit()
    row = conn.execute("SELECT * FROM lists WHERE name='Test'").fetchone()
    d = db.row_to_dict(row)
    assert isinstance(d, dict)
    assert d["name"] == "Test"
