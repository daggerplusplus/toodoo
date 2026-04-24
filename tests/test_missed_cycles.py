from datetime import date
import pytest
from unittest.mock import patch

# Import the private helper directly
from web import _missed_cycles


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
