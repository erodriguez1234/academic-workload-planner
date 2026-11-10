"""Current Canvas planning dates are explicit and deterministic with a supplied clock."""

from datetime import date, datetime, time, timezone

from workload_planner.planning_defaults import current_planning_dates


def test_current_dates_use_student_timezone_and_next_whole_minute() -> None:
    now = datetime(2026, 11, 8, 7, 59, 30, tzinfo=timezone.utc)
    assert current_planning_dates("America/Los_Angeles", now=now) == (
        date(2026, 11, 8), time(0), date(2026, 11, 21),
    )
