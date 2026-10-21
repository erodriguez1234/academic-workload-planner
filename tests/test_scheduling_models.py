"""Contracts for scheduling data, without running a scheduling algorithm."""

from dataclasses import FrozenInstanceError, fields, replace
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest

from workload_planner.scheduling_models import (
    AvailabilityPeriod, ScheduleResult, SchedulingPreferences, SchedulingTask,
    StudySession, UnscheduledReason, UnscheduledWork,
)

START = datetime(2026, 10, 10, 18, tzinfo=timezone.utc)
END = START + timedelta(hours=1)


@pytest.mark.parametrize("model", [AvailabilityPeriod, StudySession])
def test_intervals_preserve_times_and_measure_minutes(model: type) -> None:
    values = {"start_at": START, "end_at": END}
    if model is StudySession:
        values["assignment_id"] = "task-1"
    interval = model(**values)
    assert interval.start_at == START
    assert interval.end_at == END
    assert interval.duration_minutes == 60


@pytest.mark.parametrize("model", [AvailabilityPeriod, StudySession])
@pytest.mark.parametrize("field", ["start_at", "end_at"])
@pytest.mark.parametrize("value,error", [
    ("2026-10-10", TypeError), (None, TypeError),
    (START.replace(tzinfo=None), ValueError),
])
def test_intervals_require_aware_datetimes(model, field, value, error) -> None:
    values = {"start_at": START, "end_at": END}
    if model is StudySession:
        values["assignment_id"] = "task-1"
    values[field] = value
    with pytest.raises(error, match=field):
        model(**values)


@pytest.mark.parametrize("model", [AvailabilityPeriod, StudySession])
@pytest.mark.parametrize("seconds", [0, -60, 30, 90])
def test_intervals_require_positive_whole_minutes(model, seconds) -> None:
    values = {"start_at": START, "end_at": START + timedelta(seconds=seconds)}
    if model is StudySession:
        values["assignment_id"] = "task-1"
    with pytest.raises(ValueError, match="end_at"):
        model(**values)


def test_intervals_use_elapsed_time_across_offsets_and_midnight() -> None:
    start = datetime.fromisoformat("2026-10-10T23:30:00-07:00")
    end = datetime.fromisoformat("2026-10-11T07:30:00+00:00")
    assert AvailabilityPeriod(start, end).duration_minutes == 60
    assert StudySession("task-1", start, end).duration_minutes == 60


def test_elapsed_time_handles_daylight_saving_fold() -> None:
    zone = ZoneInfo("America/Los_Angeles")
    start = datetime(2026, 11, 1, 1, 30, tzinfo=zone, fold=0)
    end = datetime(2026, 11, 1, 1, 30, tzinfo=zone, fold=1)
    assert StudySession("task-1", start, end).duration_minutes == 60


def test_preferences_preserve_explicit_settings() -> None:
    zone = ZoneInfo("America/Los_Angeles")
    preferences = SchedulingPreferences(START, zone, 60, 120)
    assert preferences.planning_start == START
    assert preferences.student_timezone == zone
    assert preferences.max_session_minutes == 60
    assert preferences.daily_study_limit_minutes == 120
    # A larger session cap is harmless: the daily cap will still constrain work.
    assert replace(preferences, max_session_minutes=180).max_session_minutes == 180


@pytest.mark.parametrize("field", ["required_minutes", "max_session_minutes", "daily_study_limit_minutes", "remaining_minutes"])
@pytest.mark.parametrize("value,error", [(0, ValueError), (-1, ValueError), (True, TypeError), (False, TypeError), (30.0, TypeError), ("30", TypeError), (None, TypeError)])
def test_work_and_limits_require_positive_integers(field, value, error) -> None:
    with pytest.raises(error, match=field):
        if field == "required_minutes":
            SchedulingTask("task-1", value, END)
        elif field == "remaining_minutes":
            UnscheduledWork("task-1", value, "missing_deadline")
        else:
            values = {"planning_start": START, "student_timezone": ZoneInfo("UTC"),
                      "max_session_minutes": 60, "daily_study_limit_minutes": 120}
            values[field] = value
            SchedulingPreferences(**values)


@pytest.mark.parametrize("value,error", [(START.replace(tzinfo=None), ValueError), ("today", TypeError), (None, TypeError)])
def test_preferences_require_aware_planning_start(value, error) -> None:
    with pytest.raises(error, match="planning_start"):
        SchedulingPreferences(value, ZoneInfo("UTC"), 60, 120)


@pytest.mark.parametrize("value", ["America/Los_Angeles", timezone.utc, None])
def test_preferences_require_explicit_zoneinfo(value) -> None:
    with pytest.raises(TypeError, match="student_timezone"):
        SchedulingPreferences(START, value, 60, 120)


@pytest.mark.parametrize("deadline", [None, START - timedelta(days=1), END])
def test_task_preserves_missing_past_or_future_deadlines(deadline) -> None:
    task = SchedulingTask("task-1", 90, deadline)
    assert task.required_minutes == 90
    assert task.due_at == deadline


@pytest.mark.parametrize("value,error", [(START.replace(tzinfo=None), ValueError), ("tomorrow", TypeError)])
def test_task_validates_supplied_deadline(value, error) -> None:
    with pytest.raises(error, match="due_at"):
        SchedulingTask("task-1", 90, value)


@pytest.mark.parametrize("model", [SchedulingTask, StudySession, UnscheduledWork])
@pytest.mark.parametrize("value,error", [("", ValueError), ("  ", ValueError), (None, TypeError), (1, TypeError)])
def test_assignment_ids_must_be_nonblank_strings(model, value, error) -> None:
    with pytest.raises(error, match="assignment_id"):
        if model is SchedulingTask:
            model(value, 60, END)
        elif model is StudySession:
            model(value, START, END)
        else:
            model(value, 60, "missing_deadline")


@pytest.mark.parametrize("reason", ["missing_deadline", "deadline_not_after_start", "unplaced_by_greedy"])
def test_unscheduled_work_has_explicit_reason(reason) -> None:
    assert UnscheduledWork("task-1", 30, reason).reason == reason


@pytest.mark.parametrize("reason,error", [("", ValueError), ("impossible", ValueError), (None, TypeError)])
def test_unscheduled_work_rejects_unknown_reasons(reason, error) -> None:
    with pytest.raises(error, match="reason"):
        UnscheduledWork("task-1", 30, reason)


def test_result_accounts_for_partial_success_and_missing_deadline() -> None:
    tasks = (SchedulingTask("task-1", 90, END), SchedulingTask("task-2", 30, None))
    sessions = (StudySession("task-1", START, END),)
    remaining = (UnscheduledWork("task-1", 30, "unplaced_by_greedy"),
                 UnscheduledWork("task-2", 30, "missing_deadline"))
    result = ScheduleResult(tasks, sessions, remaining)
    assert result.tasks == tasks
    assert result.sessions == sessions
    assert result.unscheduled_work == remaining
    assert ScheduleResult((), (), ()).sessions == ()

    # One task may be fully completed across several sessions.
    midpoint = START + timedelta(minutes=30)
    complete = ScheduleResult(
        (SchedulingTask("task-1", 60, END),),
        (StudySession("task-1", START, midpoint), StudySession("task-1", midpoint, END)),
        (),
    )
    assert sum(session.duration_minutes for session in complete.sessions) == 60
    assert complete.unscheduled_work == ()
    unplaced = ScheduleResult(
        (SchedulingTask("task-2", 30, None),), (),
        (UnscheduledWork("task-2", 30, "missing_deadline"),),
    )
    assert unplaced.sessions == ()


@pytest.mark.parametrize("minutes", [59, 61])
def test_result_rejects_missing_or_excess_minutes(minutes) -> None:
    with pytest.raises(ValueError, match="account"):
        ScheduleResult((SchedulingTask("task-1", minutes, END),),
                       (StudySession("task-1", START, END),), ())


def test_result_checks_accounting_per_assignment() -> None:
    with pytest.raises(ValueError, match="account"):
        ScheduleResult((SchedulingTask("task-1", 30, END), SchedulingTask("task-2", 30, END)),
                       (StudySession("task-1", START, END),), ())


@pytest.mark.parametrize("collection", ["tasks", "sessions", "unscheduled_work"])
def test_result_rejects_wrong_collection_types_and_elements(collection) -> None:
    for invalid in ([], ("invalid",)):
        values = {"tasks": (), "sessions": (), "unscheduled_work": ()}
        values[collection] = invalid
        with pytest.raises(TypeError, match=collection):
            ScheduleResult(**values)


def test_result_rejects_duplicate_task_ids() -> None:
    task = SchedulingTask("task-1", 60, END)
    with pytest.raises(ValueError, match="duplicate"):
        ScheduleResult((task, task), (), ())


def test_result_rejects_duplicate_unscheduled_ids() -> None:
    task = SchedulingTask("task-1", 60, END)
    remaining = UnscheduledWork("task-1", 30, "unplaced_by_greedy")
    with pytest.raises(ValueError, match="duplicate"):
        ScheduleResult((task,), (), (remaining, remaining))


@pytest.mark.parametrize("collection", ["sessions", "unscheduled_work"])
def test_result_rejects_unknown_assignment_ids(collection) -> None:
    values = {"tasks": (), "sessions": (), "unscheduled_work": ()}
    values[collection] = ((StudySession("unknown", START, END),) if collection == "sessions"
                          else (UnscheduledWork("unknown", 60, "missing_deadline"),))
    with pytest.raises(ValueError, match="unknown"):
        ScheduleResult(**values)


def test_models_are_frozen() -> None:
    # Construct inside the test; no dependency on today's date.
    objects = [AvailabilityPeriod(START, END), StudySession("task-1", START, END),
               SchedulingTask("task-1", 60, END), UnscheduledWork("task-1", 60, "missing_deadline"),
               SchedulingPreferences(START, ZoneInfo("UTC"), 60, 120), ScheduleResult((), (), ())]
    for instance in objects:
        field = fields(instance)[0].name
        with pytest.raises(FrozenInstanceError):
            setattr(instance, field, None)


@pytest.mark.parametrize("reason,detail", [
    ("missing_deadline", "no deadline was supplied"),
    ("deadline_not_after_start", "deadline is at or before the planning start"),
    ("unplaced_by_greedy", "greedy scheduler left this work unplaced"),
])
def test_unscheduled_message_identifies_work_and_explains_reason(
    reason: UnscheduledReason, detail: str,
) -> None:
    work = UnscheduledWork("essay-1", 45, reason)

    assert work.message.startswith("Could not schedule 45 active working minutes")
    assert "assignment 'essay-1'" in work.message
    assert detail in work.message
    assert "impossible" not in work.message.lower()
    assert "infeasible" not in work.message.lower()
    assert "no possible" not in work.message.lower()
    assert "no feasible" not in work.message.lower()
    assert work.remaining_minutes == 45
    assert work.reason == reason
