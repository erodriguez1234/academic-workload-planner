"""Student targets preserve originals and fill residual capacity after dated work."""
from datetime import date, datetime
from zoneinfo import ZoneInfo

import pytest

from workload_planner.models import Assignment
from workload_planner.deadline_planning import DeadlineChoice, resolve_tasks, build_reviewed_schedule
from workload_planner.calendar_planning import BusyPeriod
from workload_planner.scheduling_models import AvailabilityPeriod, SchedulingPreferences, StudySession

ZONE = ZoneInfo("America/Los_Angeles")
def at(day, hour=0):
    return datetime(2026, 11, day, hour, tzinfo=ZONE)
def assignment(key, due=None):
    return Assignment(key, "Course", key, "unknown", due)


def test_manual_target_only_applies_to_missing_deadlines_and_does_not_mutate_originals():
    a, b = assignment("missing"), assignment("dated", at(14))
    tasks, windows = resolve_tasks([a,b], {"missing":60,"dated":60},
        {"missing": DeadlineChoice("manual", date(2026,11,12), "23:59"), "dated": DeadlineChoice("week", date(2026,11,9))}, ZONE,horizon_end=at(23))
    assert tasks[0].due_at == datetime(2026,11,12,23,59,tzinfo=ZONE)
    assert tasks[1].due_at == at(14) and a.due_at is None
    assert not windows


def test_week_work_fits_only_its_week_and_never_displaces_even_later_dated_work():
    work = [assignment("weekly"), assignment("dated", at(20))]
    tasks, windows = resolve_tasks(work, {"weekly":120,"dated":120}, {"weekly":DeadlineChoice("week",date(2026,11,9))}, ZONE,horizon_end=at(23))
    result = build_reviewed_schedule(tasks, [AvailabilityPeriod(at(8,18),at(8,20)),AvailabilityPeriod(at(9,18),at(9,21))],
        SchedulingPreferences(at(9),ZONE,60,180), windows)
    assert sum(s.duration_minutes for s in result.sessions if s.assignment_id == "dated") == 120
    assert sum(s.duration_minutes for s in result.sessions if s.assignment_id == "weekly") == 60
    assert result.unscheduled_work[0].remaining_minutes == 60
    assert all(s.start_at >= at(9) for s in result.sessions)
    assert result.sessions[0].assignment_id == "dated"


def test_future_module_week_cannot_be_filled_in_current_week():
    tasks, windows = resolve_tasks([assignment("weekly")], {"weekly":60}, {"weekly":DeadlineChoice("week",date(2026,11,16))}, ZONE,horizon_end=at(23))
    result=build_reviewed_schedule(tasks,[AvailabilityPeriod(at(9,18),at(9,20)),AvailabilityPeriod(at(16,18),at(16,20))],SchedulingPreferences(at(9),ZONE,60,120),windows)
    assert result.sessions[0].start_at == at(16,18)


def test_google_busy_and_booked_minutes_apply_across_both_priority_passes():
    work=[assignment("weekly"),assignment("dated",at(20))]
    tasks, windows=resolve_tasks(work,{"weekly":90,"dated":60},{"weekly":DeadlineChoice("week",date(2026,11,9))},ZONE,horizon_end=at(23))
    booked=StudySession("weekly",at(9,19),at(9,20))
    result=build_reviewed_schedule(tasks,[AvailabilityPeriod(at(9,17),at(9,22))],SchedulingPreferences(at(9),ZONE,60,120),windows,
        busy=[BusyPeriod(at(9,17),at(9,18))],booked=[booked])
    assert booked in result.sessions
    assert sum(s.duration_minutes for s in result.sessions)==120
    assert sum(w.remaining_minutes for w in result.unscheduled_work)==30
    assert not any(s.start_at == at(9,17) for s in result.sessions)


def test_unreviewed_missing_deadline_remains_explicit_and_accounted():
    tasks,windows=resolve_tasks([assignment("x")],{"x":90},{},ZONE,horizon_end=at(23))
    result=build_reviewed_schedule(tasks,[],SchedulingPreferences(at(9),ZONE,60,120),windows)
    assert result.unscheduled_work[0].reason == "missing_deadline"
    assert result.unscheduled_work[0].remaining_minutes==90


def test_ambiguous_manual_time_is_rejected_instead_of_guessing():
    with pytest.raises(ValueError):
        resolve_tasks([assignment("x")],{"x":60},{"x":DeadlineChoice("manual",date(2026,11,1),"01:30")},ZONE,horizon_end=at(23))


def test_undated_week_work_waits_until_last_dated_day_and_can_spill_into_next_week():
    work=[assignment("weekly"),assignment("dated",at(11,23))]
    tasks,windows=resolve_tasks(work,{"weekly":120,"dated":60},{"weekly":DeadlineChoice("week",date(2026,11,9))},ZONE,horizon_end=at(18))
    result=build_reviewed_schedule(tasks,[AvailabilityPeriod(at(9,18),at(9,21)),AvailabilityPeriod(at(11,18),at(11,19)),AvailabilityPeriod(at(16,18),at(16,19))],SchedulingPreferences(at(9),ZONE,60,120),windows)
    weekly=[s for s in result.sessions if s.assignment_id=="weekly"]
    assert [s.start_at for s in weekly]==[at(11,18),at(16,18)]
    assert not result.unscheduled_work
    assert work[0].due_at is None


def test_unfinished_dated_work_in_same_week_keeps_week_work_waiting():
    work=[assignment("weekly"),assignment("dated",at(11,23))]
    tasks,windows=resolve_tasks(work,{"weekly":60,"dated":180},{"weekly":DeadlineChoice("week",date(2026,11,9))},ZONE,horizon_end=at(18))
    result=build_reviewed_schedule(tasks,[AvailabilityPeriod(at(9,18),at(9,19)),AvailabilityPeriod(at(16,18),at(16,20))],SchedulingPreferences(at(9),ZONE,60,120),windows)
    assert not any(s.assignment_id=="weekly" for s in result.sessions)
    assert {w.assignment_id:w.remaining_minutes for w in result.unscheduled_work}=={"weekly":60,"dated":120}


def test_confirmed_module_membership_groups_dated_work_even_if_due_in_another_week():
    work=[assignment("weekly"),assignment("dated",at(17,23))]
    tasks,windows=resolve_tasks(work,{"weekly":60,"dated":60},{"weekly":DeadlineChoice("week",date(2026,11,9))},ZONE,horizon_end=at(23))
    result=build_reviewed_schedule(tasks,[AvailabilityPeriod(at(9,18),at(9,20)),AvailabilityPeriod(at(17,18),at(17,20))],SchedulingPreferences(at(9),ZONE,60,120),windows,assigned_weeks={"dated":date(2026,11,9)})
    assert next(s for s in result.sessions if s.assignment_id=="weekly").start_at==at(17,18)


def test_unreviewed_undated_work_does_not_block_a_reviewed_weekly_task():
    work=[assignment("weekly"),assignment("unreviewed")]
    tasks,windows=resolve_tasks(work,{"weekly":60,"unreviewed":60},{"weekly":DeadlineChoice("week",date(2026,11,9))},ZONE,horizon_end=at(23))
    result=build_reviewed_schedule(tasks,[AvailabilityPeriod(at(9,18),at(9,20))],SchedulingPreferences(at(9),ZONE,60,120),windows,assigned_weeks={"unreviewed":date(2026,11,9)})
    assert sum(s.duration_minutes for s in result.sessions)==60
    assert result.unscheduled_work[0].assignment_id=="unreviewed"
