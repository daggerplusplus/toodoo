from datetime import date
import pytest
from unittest.mock import patch

# Import the private helpers directly
from web import _missed_cycles, _parse_recurrence, _recurrence_interval


def fake_today(d: date):
    return patch("web.date") if False else d  # helper for readability


@pytest.mark.parametrize("due, today, recurrence, expected", [
    # not yet overdue
    ("2026-04-25", date(2026, 4, 21), "daily",   0),
    ("2026-04-21", date(2026, 4, 21), "weekly",  0),
    # daily
    ("2026-04-18", date(2026, 4, 21), "daily",   3),
    # weekly
    ("2026-04-07", date(2026, 4, 21), "weekly",  2),
    ("2026-04-14", date(2026, 4, 21), "weekly",  1),
    # monthly
    ("2026-02-21", date(2026, 4, 21), "monthly", 2),
    ("2026-03-22", date(2026, 4, 21), "monthly", 0),  # day not yet passed
    # yearly
    ("2024-04-21", date(2026, 4, 21), "yearly",  2),
    ("2025-04-22", date(2026, 4, 21), "yearly",  0),  # day not yet passed
])
def test_missed_cycles(due, today, recurrence, expected):
    with patch("web.date") as mock_date:
        mock_date.fromisoformat = date.fromisoformat
        mock_date.today.return_value = today
        assert _missed_cycles(due, recurrence) == expected


# ---------------------------------------------------------------------------
# _parse_recurrence
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("recurrence,expected_n,expected_unit", [
    ("daily",   1, "d"),
    ("weekly",  1, "w"),
    ("monthly", 1, "m"),
    ("yearly",  1, "y"),
    ("2w",      2, "w"),
    ("14d",    14, "d"),
    ("3m",      3, "m"),
    ("6m",      6, "m"),
    ("2y",      2, "y"),
    ("1d",      1, "d"),
    ("10d",    10, "d"),
])
def test_parse_recurrence(recurrence, expected_n, expected_unit):
    n, unit = _parse_recurrence(recurrence)
    assert n == expected_n
    assert unit == expected_unit


# ---------------------------------------------------------------------------
# _recurrence_interval
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("recurrence,advance,expected_interval", [
    # legacy aliases (advance=1)
    ("daily",   1, "+1 day"),
    ("weekly",  1, "+7 day"),
    ("monthly", 1, "+1 month"),
    ("yearly",  1, "+1 year"),
    # custom day intervals
    ("14d",  1, "+14 day"),
    ("14d",  2, "+28 day"),
    ("10d",  3, "+30 day"),
    # custom week intervals
    ("2w",   1, "+14 day"),
    ("2w",   3, "+42 day"),
    # custom month intervals
    ("3m",   1, "+3 month"),
    ("6m",   2, "+12 month"),
    # custom year intervals
    ("2y",   1, "+2 year"),
    ("2y",   3, "+6 year"),
])
def test_recurrence_interval(recurrence, advance, expected_interval):
    assert _recurrence_interval(recurrence, advance) == expected_interval


# ---------------------------------------------------------------------------
# _missed_cycles strips time component from datetime strings
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("due_with_time,due_date_only,recurrence", [
    ("2026-01-01T09:00", "2026-01-01", "daily"),
    ("2026-01-01T23:59", "2026-01-01", "weekly"),
    ("2026-01-01T00:00", "2026-01-01", "monthly"),
])
def test_missed_cycles_datetime_matches_date_only(due_with_time, due_date_only, recurrence):
    today = date(2026, 4, 25)
    with patch("web.date") as mock_date:
        mock_date.fromisoformat = date.fromisoformat
        mock_date.today.return_value = today
        assert _missed_cycles(due_with_time, recurrence) == _missed_cycles(due_date_only, recurrence)


# ---------------------------------------------------------------------------
# _missed_cycles with custom intervals
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("recurrence,days_overdue,expected", [
    # 2-week cycle: 30 days overdue → 2 full cycles (30 // 14 = 2)
    ("2w",  30, 2),
    # 2-week cycle: 13 days overdue → 0 full cycles
    ("2w",  13, 0),
    # 14d is equivalent to 2w
    ("14d", 30, 2),
    ("14d", 14, 1),
    # 60 days overdue at 14d → 4 cycles (60 // 14 = 4)
    ("14d", 60, 4),
    # 3-month cycle
    ("3m",  90, 1),   # ~3 months → 1 cycle (computed via calendar months)
    ("6m", 181, 1),   # Jan 1 + 181 days = Jul 1 = exactly 6 months
    # 2-year cycle
    ("2y", 730, 1),   # ~2 years → 1 cycle
    # 10d cycle
    ("10d", 25, 2),   # 25 // 10 = 2
    ("10d",  9, 0),
])
def test_missed_cycles_custom(recurrence, days_overdue, expected):
    due = date(2026, 1, 1)
    today = date.fromordinal(due.toordinal() + days_overdue)
    with patch("web.date") as mock_date:
        mock_date.fromisoformat = date.fromisoformat
        mock_date.today.return_value = today
        assert _missed_cycles(due.isoformat(), recurrence) == expected
