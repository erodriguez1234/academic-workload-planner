"""Behavior tests for the earliest-deadline-first scheduling baseline."""

from dataclasses import replace
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest

from workload_planner.scheduler import build_schedule
from workload_planner.scheduling_models import (
    AvailabilityPeriod,
    ScheduleResult,
    SchedulingPreferences,
    SchedulingTask,
    StudySession,
    UnscheduledReason,
    UnscheduledWork,
)

ZONE = ZoneInfo("America/Los_Angeles")


def at(day: int, hour: int, minute: int = 0) -> datetime:
    """Use fixed October 2026 dates; never read the computer's clock."""
    return datetime(2026, 10, day, hour, minute, tzinfo=ZONE)


def preferences(session_limit: int = 60, daily_limit: int = 120) -> SchedulingPreferences:
    return SchedulingPreferences(at(10, 17), ZONE, session_limit, daily_limit)


def test_places_one_task_inside_one_available_period() -> None:
    task = SchedulingTask("quiz", 30, at(10, 20))
    period = AvailabilityPeriod(at(10, 18), at(10, 19))

    result = build_schedule([task], [period], preferences())

    assert result.tasks == (task,)
    assert result.sessions == (StudySession("quiz", at(10, 18), at(10, 18, 30)),)
    assert result.unscheduled_work == ()


def test_splits_long_work_at_session_limit_with_short_final_session() -> None:
    result = build_schedule(
        [SchedulingTask("essay", 140, at(10, 23))],
        [AvailabilityPeriod(at(10, 18), at(10, 21))],
        preferences(session_limit=60, daily_limit=180),
    )
    assert result.sessions == (
        StudySession("essay", at(10, 18), at(10, 19)),
        StudySession("essay", at(10, 19), at(10, 20)),
        StudySession("essay", at(10, 20), at(10, 20, 20)),
    )
    assert result.unscheduled_work == ()


def test_continues_work_in_later_periods_without_filling_the_gap() -> None:
    result = build_schedule(
        [SchedulingTask("essay", 90, at(11, 23))],
        [AvailabilityPeriod(at(11, 18), at(11, 19)),
         AvailabilityPeriod(at(10, 18), at(10, 18, 30))],
        preferences(),
    )
    assert result.sessions == (
        StudySession("essay", at(10, 18), at(10, 18, 30)),
        StudySession("essay", at(11, 18), at(11, 19)),
    )
    assert result.unscheduled_work == ()


def test_reports_remaining_minutes_when_available_time_runs_out() -> None:
    result = build_schedule(
        [SchedulingTask("essay", 90, at(10, 23))],
        [AvailabilityPeriod(at(10, 18), at(10, 19))],
        preferences(),
    )
    assert sum(session.duration_minutes for session in result.sessions) == 60
    assert len(result.unscheduled_work) == 1
    assert result.unscheduled_work[0].assignment_id == "essay"
    assert result.unscheduled_work[0].remaining_minutes == 30
    assert result.unscheduled_work[0].reason == "unplaced_by_greedy"


def test_orders_tasks_by_deadline_and_shares_period_without_overlap() -> None:
    later = SchedulingTask("a-later", 45, at(11, 20))
    urgent = SchedulingTask("z-urgent", 30, at(10, 19))
    result = build_schedule(
        [later, urgent], [AvailabilityPeriod(at(10, 18), at(10, 20))], preferences(),
    )
    assert result.tasks == (later, urgent)  # Preserve the caller's request order.
    assert result.sessions == (
        StudySession("z-urgent", at(10, 18), at(10, 18, 30)),
        StudySession("a-later", at(10, 18, 30), at(10, 19, 15)),
    )
    assert result.unscheduled_work == ()


def test_equal_deadlines_use_assignment_id_regardless_of_input_order() -> None:
    tasks = [SchedulingTask("b", 30, at(10, 20)), SchedulingTask("a", 30, at(10, 20))]
    periods = [AvailabilityPeriod(at(10, 18), at(10, 19))]
    result = build_schedule(tasks, periods, preferences())
    reversed_result = build_schedule(list(reversed(tasks)), periods, preferences())
    assert [session.assignment_id for session in result.sessions] == ["a", "b"]
    assert result.sessions == reversed_result.sessions


def test_daily_limit_is_shared_across_tasks_and_separate_periods() -> None:
    tasks = [SchedulingTask("a", 45, at(12, 20)), SchedulingTask("b", 60, at(12, 20))]
    periods = [AvailabilityPeriod(at(10, 18), at(10, 19)),
               AvailabilityPeriod(at(10, 20), at(10, 21)),
               AvailabilityPeriod(at(11, 18), at(11, 19))]
    result = build_schedule(tasks, periods, preferences(daily_limit=75))
    assert result.sessions == (
        StudySession("a", at(10, 18), at(10, 18, 45)),
        StudySession("b", at(10, 18, 45), at(10, 19)),
        StudySession("b", at(10, 20), at(10, 20, 15)),
        StudySession("b", at(11, 18), at(11, 18, 30)),
    )
    assert result.unscheduled_work == ()


def test_daily_limit_can_be_smaller_than_maximum_session() -> None:
    result = build_schedule(
        [SchedulingTask("essay", 90, at(10, 23))],
        [AvailabilityPeriod(at(10, 18), at(10, 21))],
        preferences(session_limit=180, daily_limit=45),
    )
    assert result.sessions == (StudySession("essay", at(10, 18), at(10, 18, 45)),)
    assert result.unscheduled_work == (UnscheduledWork("essay", 45, "unplaced_by_greedy"),)


def test_clips_work_at_explicit_planning_start_and_deadline() -> None:
    settings = replace(preferences(), planning_start=at(10, 18, 15))
    result = build_schedule(
        [SchedulingTask("quiz", 60, at(10, 18, 45))],
        [AvailabilityPeriod(at(10, 18), at(10, 20))], settings,
    )
    assert result.sessions == (StudySession("quiz", at(10, 18, 15), at(10, 18, 45)),)
    assert result.unscheduled_work == (UnscheduledWork("quiz", 30, "unplaced_by_greedy"),)


@pytest.mark.parametrize("deadline,reason", [
    (None, "missing_deadline"),
    (at(10, 16), "deadline_not_after_start"),
    (at(10, 17), "deadline_not_after_start"),
])
def test_ineligible_deadlines_leave_all_work_explicitly_unscheduled(
    deadline: datetime | None, reason: UnscheduledReason,
) -> None:
    result = build_schedule(
        [SchedulingTask("task", 30, deadline)],
        [AvailabilityPeriod(at(10, 18), at(10, 20))], preferences(),
    )
    assert result.sessions == ()
    assert result.unscheduled_work == (UnscheduledWork("task", 30, reason),)


def test_cross_midnight_availability_uses_student_days_not_utc_days() -> None:
    # The entire period occurs on October 11 in UTC, but spans two local days.
    result = build_schedule(
        [SchedulingTask("essay", 90, at(12, 0))],
        [AvailabilityPeriod(at(10, 23, 30).astimezone(timezone.utc),
                            at(11, 1, 30).astimezone(timezone.utc))],
        preferences(session_limit=90, daily_limit=60),
    )
    assert result.sessions == (
        StudySession("essay", at(10, 23, 30), at(11, 0)),
        StudySession("essay", at(11, 0), at(11, 1)),
    )
    assert result.unscheduled_work == ()


def test_accepts_touching_periods_and_rejects_overlapping_ones() -> None:
    task = SchedulingTask("task", 90, at(10, 22))
    first = AvailabilityPeriod(at(10, 18), at(10, 19))
    touching = AvailabilityPeriod(at(10, 19), at(10, 20))
    assert build_schedule([task], [touching, first], preferences()).unscheduled_work == ()
    overlapping = AvailabilityPeriod(at(10, 18, 30), at(10, 20))
    with pytest.raises(ValueError, match="overlap"):
        build_schedule([task], [overlapping, first], preferences())


def test_rejects_duplicate_task_ids_before_scheduling() -> None:
    task = SchedulingTask("task", 30, at(10, 20))
    with pytest.raises(ValueError, match="duplicate"):
        build_schedule([task, task], [], preferences())


def test_empty_inputs_and_no_available_time_are_accounted_for() -> None:
    assert build_schedule([], [], preferences()).sessions == ()
    task = SchedulingTask("task", 30, at(10, 20))
    for periods in ([], [AvailabilityPeriod(at(9, 18), at(9, 20))],
                    [AvailabilityPeriod(at(11, 18), at(11, 20))]):
        result = build_schedule([task], periods, preferences())
        assert result.sessions == ()
        assert result.unscheduled_work == (UnscheduledWork("task", 30, "unplaced_by_greedy"),)


def test_subminute_capacity_is_not_rounded_up_past_deadline() -> None:
    deadline = at(10, 18, 1) + timedelta(seconds=30)
    result = build_schedule(
        [SchedulingTask("task", 2, deadline)],
        [AvailabilityPeriod(at(10, 18), at(10, 19))], preferences(),
    )
    assert result.sessions == (StudySession("task", at(10, 18), at(10, 18, 1)),)
    assert result.unscheduled_work == (UnscheduledWork("task", 1, "unplaced_by_greedy"),)


def test_deadline_priority_compares_instants_across_timezone_offsets() -> None:
    earlier = SchedulingTask("z-earlier", 30, datetime.fromisoformat("2026-10-11T02:00:00Z"))
    later = SchedulingTask("a-later", 30, at(10, 20))
    result = build_schedule(
        [later, earlier], [AvailabilityPeriod(at(10, 18), at(10, 19))], preferences(),
    )
    assert [session.assignment_id for session in result.sessions] == ["z-earlier", "a-later"]


@pytest.mark.parametrize("month,day,expected_minutes", [(3, 8, 120), (11, 1, 240)])
def test_clock_changes_use_elapsed_minutes_and_one_local_daily_total(
    month: int, day: int, expected_minutes: int,
) -> None:
    start = datetime(2026, month, day, 0, 30, tzinfo=ZONE)
    end = datetime(2026, month, day, 3, 30, tzinfo=ZONE)
    settings = SchedulingPreferences(start, ZONE, 60, 180)
    result = build_schedule(
        [SchedulingTask("task", expected_minutes, end)],
        [AvailabilityPeriod(start, end)], settings,
    )
    placed = min(expected_minutes, 180)
    assert sum(session.duration_minutes for session in result.sessions) == placed
    assert all(session.duration_minutes <= 60 for session in result.sessions)
    assert all(session.start_at.tzinfo == ZONE for session in result.sessions)
    assert all(session.end_at.astimezone(timezone.utc) <= end.astimezone(timezone.utc)
               for session in result.sessions)
    if expected_minutes > placed:
        assert result.unscheduled_work == (
            UnscheduledWork("task", expected_minutes - placed, "unplaced_by_greedy"),
        )
    else:
        assert result.unscheduled_work == ()


def test_repeatable_mixed_workload_preserves_inputs_and_all_constraints() -> None:
    tasks = [SchedulingTask("later", 200, at(12, 20)),
             SchedulingTask("urgent", 80, at(10, 19, 30)),
             SchedulingTask("undated", 30, None)]
    periods = [AvailabilityPeriod(at(11, 18), at(11, 21)),
               AvailabilityPeriod(at(10, 18), at(10, 21))]
    settings = preferences(session_limit=45, daily_limit=100)
    original_tasks, original_periods = tasks.copy(), periods.copy()
    result = build_schedule(tasks, periods, settings)
    assert result == build_schedule(tasks, periods, settings)
    assert tasks == original_tasks
    assert periods == original_periods

    assert_schedule_constraints(result, periods, settings)
    assert sum(session.duration_minutes for session in result.sessions) == 200


def assert_schedule_constraints(
    result: ScheduleResult,
    availability: list[AvailabilityPeriod],
    settings: SchedulingPreferences,
) -> None:
    """Check output contracts without using the scheduler's placement helpers.

    Compare actual UTC intervals, total minutes by local day, and account for
    each task separately. Checking the last instant before a session's end
    allows it to end exactly at midnight while staying within one local day.
    """
    requested = {task.assignment_id: task for task in result.tasks}
    accounted = dict.fromkeys(requested, 0)
    daily: dict[date, int] = {}
    planning_start = settings.planning_start.astimezone(timezone.utc)
    previous_end = planning_start
    for session in result.sessions:
        assert session.assignment_id in requested
        start = session.start_at.astimezone(timezone.utc)
        end = session.end_at.astimezone(timezone.utc)
        seconds = (end - start).total_seconds()
        assert seconds > 0 and seconds % 60 == 0
        minutes = int(seconds // 60)
        assert minutes == session.duration_minutes
        assert minutes <= settings.max_session_minutes
        assert start >= previous_end  # Also checks chronological output.
        deadline = requested[session.assignment_id].due_at
        assert deadline is not None
        assert end <= deadline.astimezone(timezone.utc)
        assert any(
            period.start_at.astimezone(timezone.utc) <= start
            and end <= period.end_at.astimezone(timezone.utc)
            for period in availability
        )
        day = start.astimezone(settings.student_timezone).date()
        last_instant = (end - timedelta(microseconds=1)).astimezone(settings.student_timezone)
        assert last_instant.date() == day
        daily[day] = daily.get(day, 0) + minutes
        accounted[session.assignment_id] += minutes
        previous_end = end
    assert all(minutes <= settings.daily_study_limit_minutes for minutes in daily.values())

    remainder_ids: set[str] = set()
    for work in result.unscheduled_work:
        assert work.assignment_id in requested
        assert work.assignment_id not in remainder_ids
        remainder_ids.add(work.assignment_id)
        assert work.remaining_minutes > 0
        accounted[work.assignment_id] += work.remaining_minutes
        task = requested[work.assignment_id]
        if task.due_at is None:
            assert work.reason == "missing_deadline"
        elif task.due_at.astimezone(timezone.utc) <= planning_start:
            assert work.reason == "deadline_not_after_start"
        else:
            assert work.reason == "unplaced_by_greedy"
        assert work.message.startswith("Could not schedule")
    for task in result.tasks:
        assert accounted[task.assignment_id] == task.required_minutes
        if task.due_at is None or task.due_at.astimezone(timezone.utc) <= planning_start:
            assert task.assignment_id in remainder_ids


@pytest.mark.parametrize("required_minutes", [1, 60, 121, 500])
@pytest.mark.parametrize("session_limit,daily_limit", [(1, 45), (60, 90), (180, 60)])
def test_constraint_matrix_with_gaps_midnight_and_overloaded_tasks(
    required_minutes: int, session_limit: int, daily_limit: int,
) -> None:
    tasks = [SchedulingTask("later", 121, at(12, 2)),
             SchedulingTask("early", required_minutes, at(10, 19, 30)),
             SchedulingTask("tied", 30, at(10, 19, 30)),
             SchedulingTask("missing", 20, None),
             SchedulingTask("overdue", 15, at(9, 20))]
    periods = [AvailabilityPeriod(at(11, 23, 30), at(12, 1, 30)),
               AvailabilityPeriod(at(10, 20), at(10, 21)),
               AvailabilityPeriod(at(10, 18), at(10, 19)),
               AvailabilityPeriod(at(9, 18), at(9, 20))]
    settings = replace(preferences(session_limit, daily_limit), planning_start=at(10, 18, 15))
    original_tasks, original_periods = tasks.copy(), periods.copy()
    result = build_schedule(tasks, periods, settings)

    assert result.tasks == tuple(tasks)
    assert result == build_schedule(tasks, periods, settings)
    assert tasks == original_tasks and periods == original_periods
    assert_schedule_constraints(result, periods, settings)


def test_overload_reports_each_assignment_and_keeps_successful_sessions() -> None:
    tasks = [SchedulingTask("essay", 90, at(10, 20)),
             SchedulingTask("quiz", 30, at(10, 20)),
             SchedulingTask("reading", 20, None),
             SchedulingTask("late", 15, at(9, 20))]
    periods = [AvailabilityPeriod(at(10, 18), at(10, 19))]
    result = build_schedule(tasks, periods, preferences())

    assert result.sessions == (StudySession("essay", at(10, 18), at(10, 19)),)
    assert {work.assignment_id: (work.remaining_minutes, work.reason)
            for work in result.unscheduled_work} == {
        "essay": (30, "unplaced_by_greedy"),
        "quiz": (30, "unplaced_by_greedy"),
        "reading": (20, "missing_deadline"),
        "late": (15, "deadline_not_after_start"),
    }
    for work in result.unscheduled_work:
        assert work.assignment_id in work.message
        assert str(work.remaining_minutes) in work.message
    assert_schedule_constraints(result, periods, preferences())


def test_task_that_misses_deadline_does_not_block_later_eligible_work() -> None:
    tasks = [SchedulingTask("early", 30, at(10, 17, 30)),
             SchedulingTask("later", 60, at(10, 20))]
    periods = [AvailabilityPeriod(at(10, 18), at(10, 19))]
    result = build_schedule(tasks, periods, preferences())

    assert result.sessions == (StudySession("later", at(10, 18), at(10, 19)),)
    assert result.unscheduled_work == (UnscheduledWork("early", 30, "unplaced_by_greedy"),)
    assert_schedule_constraints(result, periods, preferences())


def test_sessions_can_start_at_planning_start_and_end_exactly_at_deadline() -> None:
    settings = replace(preferences(), planning_start=at(10, 18))
    tasks = [SchedulingTask("quiz", 60, at(10, 19))]
    periods = [AvailabilityPeriod(at(10, 17), at(10, 19))]
    result = build_schedule(tasks, periods, settings)

    assert result.sessions == (StudySession("quiz", at(10, 18), at(10, 19)),)
    assert result.unscheduled_work == ()
    assert_schedule_constraints(result, periods, settings)


@pytest.mark.parametrize("kind", ["duplicate", "nested", "different_offsets"])
def test_rejects_complicated_overlaps_even_before_planning_start(kind: str) -> None:
    first = AvailabilityPeriod(at(9, 18), at(9, 20))
    others = {
        "duplicate": first,
        "nested": AvailabilityPeriod(at(9, 18, 30), at(9, 19)),
        "different_offsets": AvailabilityPeriod(
            at(9, 19).astimezone(timezone.utc), at(9, 21).astimezone(timezone.utc),
        ),
    }
    with pytest.raises(ValueError, match="availability periods cannot overlap"):
        build_schedule([], [others[kind], first], preferences())


def test_midnight_resets_daily_allowance_after_earlier_period_used_it() -> None:
    tasks = [SchedulingTask("task", 150, at(11, 2))]
    periods = [AvailabilityPeriod(at(10, 18), at(10, 19)),
               AvailabilityPeriod(at(10, 23, 30), at(11, 1, 30))]
    result = build_schedule(tasks, periods, preferences())

    assert result.sessions == (
        StudySession("task", at(10, 18), at(10, 19)),
        StudySession("task", at(10, 23, 30), at(11, 0)),
        StudySession("task", at(11, 0), at(11, 1)),
    )
    assert result.unscheduled_work == ()
    assert_schedule_constraints(result, periods, preferences())


def test_one_period_can_cross_several_midnights_without_exceeding_daily_limits() -> None:
    tasks = [SchedulingTask("task", 240, at(13, 0))]
    periods = [AvailabilityPeriod(at(10, 23, 30), at(12, 1))]
    settings = preferences(session_limit=120, daily_limit=60)
    result = build_schedule(tasks, periods, settings)

    assert [session.duration_minutes for session in result.sessions] == [30, 60, 60]
    assert result.unscheduled_work == (UnscheduledWork("task", 90, "unplaced_by_greedy"),)
    assert_schedule_constraints(result, periods, settings)


@pytest.mark.parametrize("month,day", [(3, 8), (11, 1)])
def test_constraint_checks_cover_daylight_saving_transitions(month: int, day: int) -> None:
    start = datetime(2026, month, day, 0, 30, tzinfo=ZONE)
    end = datetime(2026, month, day, 3, 30, tzinfo=ZONE)
    tasks = [SchedulingTask("task", 300, end)]
    periods = [AvailabilityPeriod(start, end)]
    settings = SchedulingPreferences(start, ZONE, 45, 180)
    result = build_schedule(tasks, periods, settings)

    assert result == build_schedule(tasks, periods, settings)
    assert_schedule_constraints(result, periods, settings)
