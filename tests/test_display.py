"""Readable date/time output without changing the underlying timestamps."""

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from workload_planner.display import format_datetime


@pytest.mark.parametrize("iso, expected", [
    ("2026-11-04T23:59:00-08:00", "November 4, 2026 11:59PM PST"),
    ("2026-11-04T00:00:00-08:00", "November 4, 2026 12:00AM PST"),
    ("2026-11-04T12:00:00-08:00", "November 4, 2026 12:00PM PST"),
    ("2026-11-04T09:05:00-08:00", "November 4, 2026 9:05AM PST"),
    ("2026-11-05T07:59:00Z", "November 4, 2026 11:59PM PST"),
])
def test_formats_in_student_timezone_without_leading_zeroes(iso: str, expected: str) -> None:
    value = datetime.fromisoformat(iso)
    original = value.isoformat()
    assert format_datetime(value, "America/Los_Angeles") == expected
    assert value.isoformat() == original


def test_missing_deadline_keeps_existing_label() -> None:
    assert format_datetime(None, "America/Los_Angeles") == "No deadline"


def test_repeated_local_hour_keeps_distinct_timezone_labels() -> None:
    first = datetime(2026, 11, 1, 1, 30, tzinfo=ZoneInfo("America/Los_Angeles"), fold=0)
    second = first.replace(fold=1)
    assert format_datetime(first) == "November 1, 2026 1:30AM PDT"
    assert format_datetime(second) == "November 1, 2026 1:30AM PST"


def test_invalid_timezone_during_editing_keeps_source_timezone() -> None:
    value = datetime.fromisoformat("2026-11-05T07:59:00Z")
    assert format_datetime(value, "Not/AZone") == "November 5, 2026 7:59AM UTC"
