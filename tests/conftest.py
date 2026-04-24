import os
import tempfile
import pytest
from fastapi.testclient import TestClient

# Use a temp DB so tests never touch the real todo.db
@pytest.fixture(scope="session", autouse=True)
def tmp_db():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    os.environ["TODO_DB"] = db_path
    yield db_path
    os.unlink(db_path)


@pytest.fixture
def client(tmp_db):
    import db as db_module
    db_module.DB_PATH = tmp_db
    db_module.init_db()
    from web import app
    with TestClient(app) as c:
        yield c
