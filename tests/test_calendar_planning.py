"""Busy-time subtraction and retained bookings, independent of Google HTTP."""

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from workload_planner.calendar_planning import BusyPeriod, build_calendar_schedule, subtract_busy
from workload_planner.scheduling_models import AvailabilityPeriod, SchedulingPreferences, SchedulingTask, StudySession

ZONE = ZoneInfo("America/Los_Angeles")


def at(hour: int, minute: int = 0, second: int = 0, day: int = 9) -> datetime:
    return datetime(2026, 11, day, hour, minute, second, tzinfo=ZONE)


def test_busy_meeting_splits_available_time_and_touching_events_do_not_block_extra() -> None:
    original = [AvailabilityPeriod(at(9), at(13))]
    result = subtract_busy(original, [BusyPeriod(at(10), at(11)), BusyPeriod(at(13), at(14))])
    assert result == (AvailabilityPeriod(at(9), at(10)), AvailabilityPeriod(at(11), at(13)))
    assert original == [AvailabilityPeriod(at(9), at(13))]


def test_overlapping_busy_times_merge_and_full_day_leaves_no_capacity() -> None:
    assert subtract_busy([AvailabilityPeriod(at(9), at(12))], [BusyPeriod(at(8), at(10)), BusyPeriod(at(9), at(13))]) == ()


def test_fractional_minute_busy_boundaries_are_rounded_outward() -> None:
    assert subtract_busy([AvailabilityPeriod(at(9), at(10))], [BusyPeriod(at(9, 20, 20), at(9, 30, 10))]) == (
        AvailabilityPeriod(at(9), at(9, 20)), AvailabilityPeriod(at(9, 31), at(10)),
    )


def test_existing_booked_work_counts_toward_requested_minutes_and_daily_limit() -> None:
    booked = StudySession("task", at(11), at(12))
    settings = SchedulingPreferences(at(8), ZONE, 60, 120)
    result = build_calendar_schedule(
        [SchedulingTask("task", 150, at(20))], [AvailabilityPeriod(at(9), at(14))], settings,
        [BusyPeriod(at(10), at(11))], [booked],
    )
    assert sum(s.duration_minutes for s in result.sessions) == 120
    assert result.unscheduled_work[0].remaining_minutes == 30
    assert booked in result.sessions
    assert StudySession("task", at(9), at(10)) in result.sessions


def test_other_assignment_bookings_also_use_daily_study_budget() -> None:
    result = build_calendar_schedule(
        [SchedulingTask("new", 90, at(20))], [AvailabilityPeriod(at(9), at(14))],
        SchedulingPreferences(at(8), ZONE, 60, 90), [], [StudySession("old", at(12), at(13))],
    )
    assert sum(s.duration_minutes for s in result.sessions) == 30
    assert result.unscheduled_work[0].remaining_minutes == 60


def test_busy_all_day_preserves_every_requested_minute_as_unscheduled() -> None:
    result = build_calendar_schedule(
        [SchedulingTask("task", 90, at(20))], [AvailabilityPeriod(at(9), at(14))],
        SchedulingPreferences(at(8), ZONE, 60, 120), [BusyPeriod(at(0), at(0, day=10))], [],
    )
    assert not result.sessions and result.unscheduled_work[0].remaining_minutes == 90


@pytest.mark.parametrize("booked", [StudySession("task", at(7), at(9)), StudySession("task", at(20), at(21))])
def test_changed_or_in_progress_bookings_require_review(booked: StudySession) -> None:
    with pytest.raises(ValueError, match="existing"):
        build_calendar_schedule([SchedulingTask("task", 90, at(20))], [], SchedulingPreferences(at(8), ZONE, 60, 120), [], [booked])


def test_retained_bookings_cannot_exceed_adjusted_workload() -> None:
    with pytest.raises(ValueError, match="minutes"):
        build_calendar_schedule([SchedulingTask("task", 30, at(20))], [], SchedulingPreferences(at(8), ZONE, 60, 120), [], [StudySession("task", at(9), at(10))])


def test_time_before_planning_start_does_not_consume_daily_budget() -> None:
    result = build_calendar_schedule(
        [SchedulingTask("task", 90, at(20))], [AvailabilityPeriod(at(9), at(18))],
        SchedulingPreferences(at(15), ZONE, 60, 90), [], [],
    )
    assert sum(s.duration_minutes for s in result.sessions) == 90
    assert result.sessions[0].start_at == at(15)


def test_clock_change_busy_interval_is_subtracted_by_elapsed_time() -> None:
    # Repeated 1AM on the November 1 fall-back day is two distinct instants.
    start = datetime(2026, 11, 1, 0, tzinfo=ZONE)
    end = datetime(2026, 11, 1, 3, tzinfo=ZONE)
    first = datetime(2026, 11, 1, 1, 15, tzinfo=ZONE, fold=0)
    second = datetime(2026, 11, 1, 1, 45, tzinfo=ZONE, fold=1)
    free = subtract_busy([AvailabilityPeriod(start, end)], [BusyPeriod(first, second)])
    assert sum(p.duration_minutes for p in free) == 150
