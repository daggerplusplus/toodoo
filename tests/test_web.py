import pytest


# ---------------------------------------------------------------------------
# Lists
# ---------------------------------------------------------------------------

def test_get_lists_returns_seeded(client):
    r = client.get("/api/lists")
    assert r.status_code == 200
    names = [l["name"] for l in r.json()]
    assert "My Day" in names
    assert "Tasks" in names


def test_create_list(client):
    r = client.post("/api/lists", json={"name": "Work", "icon": "💼"})
    assert r.status_code == 201
    body = r.json()
    assert body["name"] == "Work"
    assert body["icon"] == "💼"
    assert "id" in body


def test_create_list_auto_color(client):
    r = client.post("/api/lists", json={"name": "Auto"})
    assert r.status_code == 201
    assert r.json()["color"].startswith("#")


def test_delete_list(client):
    r = client.post("/api/lists", json={"name": "Temp"})
    list_id = r.json()["id"]
    r = client.delete(f"/api/lists/{list_id}")
    assert r.status_code == 204
    ids = [l["id"] for l in client.get("/api/lists").json()]
    assert list_id not in ids


def test_delete_list_not_found(client):
    r = client.delete("/api/lists/99999")
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# Tasks
# ---------------------------------------------------------------------------

@pytest.fixture
def list_id(client):
    r = client.post("/api/lists", json={"name": "Test List"})
    return r.json()["id"]


def test_add_task(client, list_id):
    r = client.post(f"/api/lists/{list_id}/tasks", json={"title": "Buy milk"})
    assert r.status_code == 201
    body = r.json()
    assert body["title"] == "Buy milk"
    assert body["done"] == 0
    assert body["starred"] == 0


def test_get_tasks(client, list_id):
    client.post(f"/api/lists/{list_id}/tasks", json={"title": "Task A"})
    r = client.get(f"/api/lists/{list_id}/tasks")
    assert r.status_code == 200
    titles = [t["title"] for t in r.json()]
    assert "Task A" in titles


def test_get_tasks_excludes_done_by_default(client, list_id):
    r = client.post(f"/api/lists/{list_id}/tasks", json={"title": "Done Task"})
    task_id = r.json()["id"]
    client.post(f"/api/tasks/{task_id}/toggle")
    r = client.get(f"/api/lists/{list_id}/tasks")
    titles = [t["title"] for t in r.json()]
    assert "Done Task" not in titles


def test_get_tasks_include_done(client, list_id):
    r = client.post(f"/api/lists/{list_id}/tasks", json={"title": "Done Task 2"})
    task_id = r.json()["id"]
    client.post(f"/api/tasks/{task_id}/toggle")
    r = client.get(f"/api/lists/{list_id}/tasks", params={"include_done": True})
    titles = [t["title"] for t in r.json()]
    assert "Done Task 2" in titles


def test_get_tasks_list_not_found(client):
    r = client.get("/api/lists/99999/tasks")
    assert r.status_code == 404


def test_add_task_list_not_found(client):
    r = client.post("/api/lists/99999/tasks", json={"title": "Ghost"})
    assert r.status_code == 404


def test_update_task(client, list_id):
    r = client.post(f"/api/lists/{list_id}/tasks", json={"title": "Old title"})
    task_id = r.json()["id"]
    r = client.patch(f"/api/tasks/{task_id}", json={"title": "New title"})
    assert r.status_code == 200
    assert r.json()["title"] == "New title"


def test_update_task_not_found(client):
    r = client.patch("/api/tasks/99999", json={"title": "X"})
    assert r.status_code == 404


def test_update_task_no_fields(client, list_id):
    r = client.post(f"/api/lists/{list_id}/tasks", json={"title": "Unchanged"})
    task_id = r.json()["id"]
    r = client.patch(f"/api/tasks/{task_id}", json={})
    assert r.status_code == 200
    assert r.json()["title"] == "Unchanged"


def test_delete_task(client, list_id):
    r = client.post(f"/api/lists/{list_id}/tasks", json={"title": "Delete me"})
    task_id = r.json()["id"]
    r = client.delete(f"/api/tasks/{task_id}")
    assert r.status_code == 204


def test_delete_task_not_found(client):
    r = client.delete("/api/tasks/99999")
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# Toggle / Star
# ---------------------------------------------------------------------------

def test_toggle_task_done(client, list_id):
    r = client.post(f"/api/lists/{list_id}/tasks", json={"title": "Toggle me"})
    task_id = r.json()["id"]
    r = client.post(f"/api/tasks/{task_id}/toggle")
    assert r.status_code == 200
    assert r.json()["done"] == 1


def test_toggle_task_undone(client, list_id):
    r = client.post(f"/api/lists/{list_id}/tasks", json={"title": "Toggle back"})
    task_id = r.json()["id"]
    client.post(f"/api/tasks/{task_id}/toggle")
    r = client.post(f"/api/tasks/{task_id}/toggle")
    assert r.json()["done"] == 0


def test_toggle_task_not_found(client):
    r = client.post("/api/tasks/99999/toggle")
    assert r.status_code == 404


def test_star_task(client, list_id):
    r = client.post(f"/api/lists/{list_id}/tasks", json={"title": "Star me"})
    task_id = r.json()["id"]
    r = client.post(f"/api/tasks/{task_id}/star")
    assert r.status_code == 200
    assert r.json()["starred"] == 1


def test_unstar_task(client, list_id):
    r = client.post(f"/api/lists/{list_id}/tasks", json={"title": "Unstar me"})
    task_id = r.json()["id"]
    client.post(f"/api/tasks/{task_id}/star")
    r = client.post(f"/api/tasks/{task_id}/star")
    assert r.json()["starred"] == 0


def test_star_task_not_found(client):
    r = client.post("/api/tasks/99999/star")
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# Sorting
# ---------------------------------------------------------------------------

def test_default_sort_due_dates_before_no_dates(client, list_id):
    client.post(f"/api/lists/{list_id}/tasks", json={"title": "No date A"})
    client.post(f"/api/lists/{list_id}/tasks", json={"title": "Has date", "due_date": "2030-01-15"})
    client.post(f"/api/lists/{list_id}/tasks", json={"title": "No date B"})
    titles = [t["title"] for t in client.get(f"/api/lists/{list_id}/tasks").json()]
    assert titles.index("Has date") < titles.index("No date B")


def test_sort_due_date_orders_by_due_date_asc(client, list_id):
    client.post(f"/api/lists/{list_id}/tasks", json={"title": "Later", "due_date": "2030-06-01"})
    client.post(f"/api/lists/{list_id}/tasks", json={"title": "Earlier", "due_date": "2030-01-01"})
    client.post(f"/api/lists/{list_id}/tasks", json={"title": "No date"})
    r = client.get(f"/api/lists/{list_id}/tasks", params={"sort": "due_date"})
    titles = [t["title"] for t in r.json()]
    assert titles.index("Earlier") < titles.index("Later")
    assert titles.index("Later") < titles.index("No date")


def test_sort_due_date_nulls_last(client, list_id):
    client.post(f"/api/lists/{list_id}/tasks", json={"title": "No date"})
    client.post(f"/api/lists/{list_id}/tasks", json={"title": "Has date", "due_date": "2030-03-01"})
    r = client.get(f"/api/lists/{list_id}/tasks", params={"sort": "due_date"})
    titles = [t["title"] for t in r.json()]
    assert titles.index("Has date") < titles.index("No date")


# ---------------------------------------------------------------------------
# Clear completed
# ---------------------------------------------------------------------------

def test_clear_completed_removes_done_tasks(client, list_id):
    r = client.post(f"/api/lists/{list_id}/tasks", json={"title": "Done task"})
    task_id = r.json()["id"]
    client.post(f"/api/tasks/{task_id}/toggle")
    client.post(f"/api/lists/{list_id}/tasks", json={"title": "Pending task"})
    r = client.delete(f"/api/lists/{list_id}/tasks/completed")
    assert r.status_code == 200
    assert r.json()["cleared"] == 1
    titles = [t["title"] for t in client.get(f"/api/lists/{list_id}/tasks?include_done=true").json()]
    assert "Done task" not in titles
    assert "Pending task" in titles


def test_clear_completed_preserves_task_log(client, list_id):
    r = client.post(f"/api/lists/{list_id}/tasks", json={"title": "Log survivor"})
    task_id = r.json()["id"]
    client.post(f"/api/tasks/{task_id}/toggle")
    client.delete(f"/api/lists/{list_id}/tasks/completed")
    log_titles = [e["task_title"] for e in client.get("/api/log").json()]
    assert "Log survivor" in log_titles


def test_clear_completed_returns_zero_when_none(client, list_id):
    client.post(f"/api/lists/{list_id}/tasks", json={"title": "Still pending"})
    r = client.delete(f"/api/lists/{list_id}/tasks/completed")
    assert r.status_code == 200
    assert r.json()["cleared"] == 0


def test_clear_completed_list_not_found(client):
    r = client.delete("/api/lists/99999/tasks/completed")
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# Skip
# ---------------------------------------------------------------------------

def test_skip_recurring_task_advances_due_date(client, list_id):
    r = client.post(f"/api/lists/{list_id}/tasks", json={
        "title": "Skip me",
        "due_date": "2026-04-14",
        "recurrence": "weekly",
    })
    task_id = r.json()["id"]
    r = client.post(f"/api/tasks/{task_id}/skip", json={})
    assert r.status_code == 200
    body = r.json()
    assert body["done"] == 0
    assert body["due_date"] != "2026-04-14"


def test_skip_logs_to_activity_log_with_skipped_flag(client, list_id):
    r = client.post(f"/api/lists/{list_id}/tasks", json={
        "title": "Skip logged",
        "due_date": "2026-04-14",
        "recurrence": "daily",
    })
    task_id = r.json()["id"]
    client.post(f"/api/tasks/{task_id}/skip", json={"reason": "too tired"})
    log = client.get("/api/log").json()
    entry = next((e for e in log if e["task_title"] == "Skip logged"), None)
    assert entry is not None
    assert entry["skipped"] == 1
    assert entry["reason"] == "too tired"


def test_skip_without_reason(client, list_id):
    r = client.post(f"/api/lists/{list_id}/tasks", json={
        "title": "Skip no reason",
        "due_date": "2026-04-14",
        "recurrence": "daily",
    })
    task_id = r.json()["id"]
    r = client.post(f"/api/tasks/{task_id}/skip", json={})
    assert r.status_code == 200
    log = client.get("/api/log").json()
    entry = next((e for e in log if e["task_title"] == "Skip no reason"), None)
    assert entry["skipped"] == 1
    assert entry["reason"] is None


def test_skip_non_recurring_task_returns_400(client, list_id):
    r = client.post(f"/api/lists/{list_id}/tasks", json={"title": "Not recurring"})
    task_id = r.json()["id"]
    r = client.post(f"/api/tasks/{task_id}/skip", json={})
    assert r.status_code == 400


def test_skip_task_not_found(client):
    r = client.post("/api/tasks/99999/skip", json={})
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# Recurrence
# ---------------------------------------------------------------------------

def test_toggle_recurring_task_advances_due_date(client, list_id):
    r = client.post(f"/api/lists/{list_id}/tasks", json={
        "title": "Weekly chore",
        "due_date": "2026-04-14",
        "recurrence": "weekly",
    })
    task_id = r.json()["id"]
    r = client.post(f"/api/tasks/{task_id}/toggle")
    body = r.json()
    # recurring tasks stay undone and get their due date advanced
    assert body["done"] == 0
    assert body["due_date"] != "2026-04-14"


@pytest.mark.parametrize("recurrence,due_date,expected_due", [
    # 2w → advances by 14 days from 2026-04-14
    ("2w",  "2026-04-14", "2026-04-28"),
    # 14d → same as 2w
    ("14d", "2026-04-14", "2026-04-28"),
    # 3m → advances by 3 months
    ("3m",  "2026-04-14", "2026-07-14"),
    # 2y → advances by 2 years
    ("2y",  "2026-04-14", "2028-04-14"),
])
def test_toggle_custom_recurrence_advances_due_date_correctly(client, list_id, recurrence, due_date, expected_due):
    r = client.post(f"/api/lists/{list_id}/tasks", json={
        "title": f"Custom recur {recurrence}",
        "due_date": due_date,
        "recurrence": recurrence,
    })
    task_id = r.json()["id"]
    r = client.post(f"/api/tasks/{task_id}/toggle")
    body = r.json()
    assert body["done"] == 0
    assert body["due_date"] == expected_due


@pytest.mark.parametrize("recurrence,due_date,expected_due", [
    ("2w",  "2026-04-14", "2026-04-28"),
    ("14d", "2026-04-14", "2026-04-28"),
    ("3m",  "2026-04-14", "2026-07-14"),
])
def test_skip_custom_recurrence_advances_due_date_correctly(client, list_id, recurrence, due_date, expected_due):
    r = client.post(f"/api/lists/{list_id}/tasks", json={
        "title": f"Skip custom {recurrence}",
        "due_date": due_date,
        "recurrence": recurrence,
    })
    task_id = r.json()["id"]
    r = client.post(f"/api/tasks/{task_id}/skip", json={})
    body = r.json()
    assert body["done"] == 0
    assert body["due_date"] == expected_due


# ---------------------------------------------------------------------------
# Log
# ---------------------------------------------------------------------------

def test_get_log(client):
    r = client.get("/api/log")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


# ---------------------------------------------------------------------------
# Export / Import
# ---------------------------------------------------------------------------

def test_export_returns_all_tables(client, list_id):
    client.post(f"/api/lists/{list_id}/tasks", json={"title": "Export me"})
    r = client.get("/api/export")
    assert r.status_code == 200
    data = r.json()
    assert data["version"] == 1
    assert "exported_at" in data
    list_ids = [l["id"] for l in data["lists"]]
    assert list_id in list_ids
    titles = [t["title"] for t in data["tasks"]]
    assert "Export me" in titles


def test_export_includes_task_log(client, list_id):
    r = client.post(f"/api/lists/{list_id}/tasks", json={"title": "Log me"})
    task_id = r.json()["id"]
    client.post(f"/api/tasks/{task_id}/toggle")
    data = client.get("/api/export").json()
    log_titles = [e["task_title"] for e in data["task_log"]]
    assert "Log me" in log_titles


def test_import_restores_data(client, list_id):
    lists_before = client.get("/api/lists").json()
    list_name = next(l["name"] for l in lists_before if l["id"] == list_id)
    client.post(f"/api/lists/{list_id}/tasks", json={"title": "Survive import"})
    backup = client.get("/api/export").json()
    client.delete(f"/api/lists/{list_id}")
    r = client.post("/api/import", json=backup)
    assert r.status_code == 200
    assert r.json()["imported"]["lists"] >= 1
    list_names = [l["name"] for l in client.get("/api/lists").json()]
    assert list_name in list_names


def test_import_rejects_bad_version(client):
    r = client.post("/api/import", json={"version": 99, "lists": [], "tasks": [], "task_log": []})
    assert r.status_code == 422


def test_import_is_idempotent(client, list_id):
    backup = client.get("/api/export").json()
    r1 = client.post("/api/import", json=backup)
    r2 = client.post("/api/import", json=backup)
    assert r1.json()["imported"]["lists"] == r2.json()["imported"]["lists"]
    assert r1.json()["imported"]["tasks"] == r2.json()["imported"]["tasks"]


# ---------------------------------------------------------------------------
# Categories
# ---------------------------------------------------------------------------

def test_create_category(client):
    r = client.post("/api/categories", json={"name": "Work"})
    assert r.status_code == 201
    body = r.json()
    assert body["name"] == "Work"
    assert "id" in body


def test_get_categories(client):
    client.post("/api/categories", json={"name": "Alpha"})
    r = client.get("/api/categories")
    assert r.status_code == 200
    assert any(c["name"] == "Alpha" for c in r.json())


def test_rename_category(client):
    r = client.post("/api/categories", json={"name": "OldName"})
    cat_id = r.json()["id"]
    r = client.patch(f"/api/categories/{cat_id}", json={"name": "NewName"})
    assert r.status_code == 200
    assert r.json()["name"] == "NewName"


def test_delete_category_uncategorizes_lists(client):
    cat_id = client.post("/api/categories", json={"name": "Tmp"}).json()["id"]
    list_id = client.post("/api/lists", json={"name": "Scoped"}).json()["id"]
    client.patch(f"/api/lists/{list_id}", json={"category_id": cat_id})
    client.delete(f"/api/categories/{cat_id}")
    lists = client.get("/api/lists").json()
    match = next(l for l in lists if l["id"] == list_id)
    assert match["category_id"] is None


def test_category_not_found(client):
    assert client.patch("/api/categories/99999", json={"name": "X"}).status_code == 404
    assert client.delete("/api/categories/99999").status_code == 404


# ---------------------------------------------------------------------------
# List patch & reorder
# ---------------------------------------------------------------------------

def test_patch_list_assign_category(client):
    cat_id = client.post("/api/categories", json={"name": "Cat"}).json()["id"]
    list_id = client.post("/api/lists", json={"name": "PatchMe"}).json()["id"]
    r = client.patch(f"/api/lists/{list_id}", json={"category_id": cat_id})
    assert r.status_code == 200
    assert r.json()["category_id"] == cat_id


def test_patch_list_clear_category(client):
    cat_id = client.post("/api/categories", json={"name": "CatX"}).json()["id"]
    list_id = client.post("/api/lists", json={"name": "ClearMe"}).json()["id"]
    client.patch(f"/api/lists/{list_id}", json={"category_id": cat_id})
    r = client.patch(f"/api/lists/{list_id}", json={"category_id": None})
    assert r.status_code == 200
    assert r.json()["category_id"] is None


def test_reorder_lists(client):
    a = client.post("/api/lists", json={"name": "RLA"}).json()["id"]
    b = client.post("/api/lists", json={"name": "RLB"}).json()["id"]
    c_id = client.post("/api/lists", json={"name": "RLC"}).json()["id"]
    assert client.post("/api/lists/reorder", json={"ids": [c_id, a, b]}).status_code == 204
    names = [l["name"] for l in client.get("/api/lists").json() if l["name"] in ("RLA", "RLB", "RLC")]
    assert names == ["RLC", "RLA", "RLB"]


def test_reorder_tasks(client, list_id):
    t1 = client.post(f"/api/lists/{list_id}/tasks", json={"title": "RT1"}).json()["id"]
    t2 = client.post(f"/api/lists/{list_id}/tasks", json={"title": "RT2"}).json()["id"]
    t3 = client.post(f"/api/lists/{list_id}/tasks", json={"title": "RT3"}).json()["id"]
    assert client.post(f"/api/lists/{list_id}/tasks/reorder", json={"ids": [t3, t1, t2]}).status_code == 204
    titles = [t["title"] for t in client.get(f"/api/lists/{list_id}/tasks").json()]
    assert titles == ["RT3", "RT1", "RT2"]


def test_add_task_sort_order_increments(client, list_id):
    t1 = client.post(f"/api/lists/{list_id}/tasks", json={"title": "SO1"}).json()
    t2 = client.post(f"/api/lists/{list_id}/tasks", json={"title": "SO2"}).json()
    assert t2["sort_order"] > t1["sort_order"]


# ---------------------------------------------------------------------------
# Datetime due_date (YYYY-MM-DDTHH:MM)
# ---------------------------------------------------------------------------

def test_create_task_with_datetime_due_date(client, list_id):
    r = client.post(f"/api/lists/{list_id}/tasks", json={
        "title": "Timed task",
        "due_date": "2099-06-01T14:30",
    })
    assert r.status_code == 201
    body = r.json()
    assert body["due_date"] == "2099-06-01T14:30"


def test_toggle_recurring_task_with_datetime_preserves_time(client, list_id):
    r = client.post(f"/api/lists/{list_id}/tasks", json={
        "title": "Timed recurring",
        "due_date": "2026-04-14T14:30",
        "recurrence": "weekly",
    })
    task_id = r.json()["id"]
    r = client.post(f"/api/tasks/{task_id}/toggle")
    assert r.status_code == 200
    body = r.json()
    assert body["done"] == 0
    assert "T14:30" in body["due_date"]
    assert body["due_date"] != "2026-04-14T14:30"


# ---------------------------------------------------------------------------
# UI
# ---------------------------------------------------------------------------

def test_serve_ui(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]
