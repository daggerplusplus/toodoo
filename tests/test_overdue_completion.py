"""
Tests for recurring task due-date advancement when completing overdue tasks.

All tests mock web.date.today() so results are deterministic regardless of when
the tests are run. The fixed "today" is 2026-04-27 (Monday).
"""
from datetime import date, timedelta
from unittest.mock import patch

import pytest

TODAY = date(2026, 4, 27)  # Monday


def patch_today():
    """Return a patch context manager that fixes web.date.today() to TODAY."""
    p = patch("web.date")

    class _Ctx:
        def __enter__(self):
            self._mock = p.__enter__()
            self._mock.today.return_value = TODAY
            self._mock.fromisoformat = date.fromisoformat
            return self

        def __exit__(self, *args):
            p.__exit__(*args)

    return _Ctx()


# ---------------------------------------------------------------------------
# Daily recurrence — completing on-time or overdue
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("days_overdue,expected_days_from_today", [
    # On-time (due today): advance 1 → tomorrow
    (0, 1),
    # Overdue: advance to today (the "missed" occurrence lands on today exactly)
    (1, 0),
    (2, 0),
    (5, 0),
    (10, 0),
    (30, 0),
])
def test_daily_complete_advances_correctly(client, list_id, days_overdue, expected_days_from_today):
    """Daily recurring task: on-time completion → tomorrow; overdue completion → today."""
    due = (TODAY - timedelta(days=days_overdue)).isoformat()
    r = client.post(f"/api/lists/{list_id}/tasks", json={
        "title": f"Daily overdue by {days_overdue}d",
        "due_date": due,
        "recurrence": "daily",
    })
    task_id = r.json()["id"]
    with patch_today():
        r = client.post(f"/api/tasks/{task_id}/toggle")

    body = r.json()
    assert body["done"] == 0
    expected = (TODAY + timedelta(days=expected_days_from_today)).isoformat()
    assert body["due_date"] == expected, (
        f"Daily task overdue by {days_overdue} days: expected {expected}, got {body['due_date']}"
    )


# ---------------------------------------------------------------------------
# Weekly recurrence — schedule-anchored behaviour
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("days_overdue,expected_days_from_today", [
    # On-time: due today → next in 7 days
    (0, 7),
    # Overdue 1 day: schedule-anchored → today-1 + 7 = today+6
    (1, 6),
    # Overdue 5 days: schedule-anchored → today-5 + 7 = today+2
    (5, 2),
    # Overdue 6 days: → today-6 + 7 = today+1 (tomorrow)
    (6, 1),
    # Overdue exactly 7 days: ceil(7/7)=1 advance → today-7 + 7 = today (lands on today)
    (7, 0),
    # Overdue 8 days: ceil(8/7)=2 advances → today-8 + 14 = today+6
    (8, 6),
    # Overdue 13 days: ceil(13/7)=2 advances → today-13 + 14 = today+1
    (13, 1),
    # Overdue exactly 14 days: ceil(14/7)=2 advances → today-14 + 14 = today
    (14, 0),
])
def test_weekly_complete_schedule_anchored(client, list_id, days_overdue, expected_days_from_today):
    """
    Weekly tasks are schedule-anchored: new due date is the earliest scheduled
    occurrence on or after today. Exact multiples of 7 days overdue land on today;
    other amounts land in the near future.
    """
    due = (TODAY - timedelta(days=days_overdue)).isoformat()
    r = client.post(f"/api/lists/{list_id}/tasks", json={
        "title": f"Weekly overdue by {days_overdue}d",
        "due_date": due,
        "recurrence": "weekly",
    })
    task_id = r.json()["id"]
    with patch_today():
        r = client.post(f"/api/tasks/{task_id}/toggle")

    body = r.json()
    assert body["done"] == 0
    expected_due = (TODAY + timedelta(days=expected_days_from_today)).isoformat()
    assert body["due_date"] == expected_due, (
        f"Weekly task overdue by {days_overdue}d: expected {expected_due} "
        f"(+{expected_days_from_today}d from today), got {body['due_date']}"
    )


# ---------------------------------------------------------------------------
# Custom intervals
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("recurrence,days_overdue,expected_days_from_today", [
    # 2-week cycle, 10 days overdue: ceil(10/14)=1 → today-10+14 = today+4
    ("2w",  10, 4),
    # 2-week cycle, exactly 14 days overdue: ceil(14/14)=1 → today-14+14 = today (lands on today)
    ("2w",  14, 0),
    # 14d behaves identically to 2w
    ("14d", 10, 4),
    ("14d", 14, 0),
    # 10d, 9 days overdue: ceil(9/10)=1 → today-9+10 = today+1
    ("10d",  9, 1),
    # 10d, exactly 10 days overdue: ceil(10/10)=1 → today-10+10 = today
    ("10d", 10, 0),
    # 10d, 19 days overdue: ceil(19/10)=2 → today-19+20 = today+1
    ("10d", 19, 1),
])
def test_custom_interval_complete_overdue(client, list_id, recurrence, days_overdue, expected_days_from_today):
    due = (TODAY - timedelta(days=days_overdue)).isoformat()
    r = client.post(f"/api/lists/{list_id}/tasks", json={
        "title": f"{recurrence} overdue by {days_overdue}d",
        "due_date": due,
        "recurrence": recurrence,
    })
    task_id = r.json()["id"]
    with patch_today():
        r = client.post(f"/api/tasks/{task_id}/toggle")

    body = r.json()
    assert body["done"] == 0
    expected_due = (TODAY + timedelta(days=expected_days_from_today)).isoformat()
    assert body["due_date"] == expected_due, (
        f"{recurrence} overdue by {days_overdue}d: expected {expected_due} "
        f"(+{expected_days_from_today}d from today), got {body['due_date']}"
    )


# ---------------------------------------------------------------------------
# Datetime (with time component) — time must be preserved
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("days_overdue,expected_days_from_today", [
    (0, 1),   # on-time → tomorrow
    (1, 0),   # overdue → today
    (5, 0),   # overdue → today
])
def test_daily_datetime_preserves_time_and_advances_correctly(client, list_id, days_overdue, expected_days_from_today):
    due_datetime = f"{(TODAY - timedelta(days=days_overdue)).isoformat()}T09:30"
    r = client.post(f"/api/lists/{list_id}/tasks", json={
        "title": f"Timed daily overdue {days_overdue}d",
        "due_date": due_datetime,
        "recurrence": "daily",
    })
    task_id = r.json()["id"]
    with patch_today():
        r = client.post(f"/api/tasks/{task_id}/toggle")

    body = r.json()
    assert body["done"] == 0
    expected = f"{(TODAY + timedelta(days=expected_days_from_today)).isoformat()}T09:30"
    assert body["due_date"] == expected, (
        f"Timed daily overdue {days_overdue}d: expected {expected}, got {body['due_date']}"
    )


# ---------------------------------------------------------------------------
# Skip — same advance logic as complete
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("days_overdue,expected_days_from_today", [
    (0, 1),   # on-time skip → tomorrow
    (1, 0),   # overdue skip → today
    (6, 0),   # overdue skip → today
])
def test_daily_skip_advances_correctly(client, list_id, days_overdue, expected_days_from_today):
    due = (TODAY - timedelta(days=days_overdue)).isoformat()
    r = client.post(f"/api/lists/{list_id}/tasks", json={
        "title": f"Skip daily overdue {days_overdue}d",
        "due_date": due,
        "recurrence": "daily",
    })
    task_id = r.json()["id"]
    with patch_today():
        r = client.post(f"/api/tasks/{task_id}/skip", json={})

    body = r.json()
    expected = (TODAY + timedelta(days=expected_days_from_today)).isoformat()
    assert body["due_date"] == expected
