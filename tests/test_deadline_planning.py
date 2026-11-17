"""Manual deadlines change scheduling inputs without changing imported assignments."""
from datetime import date, datetime
from zoneinfo import ZoneInfo

import pytest

from workload_planner.models import Assignment
from workload_planner.deadline_planning import DeadlineChoice, resolve_tasks
from workload_planner.scheduler import build_schedule
from workload_planner.scheduling_models import AvailabilityPeriod, SchedulingPreferences

ZONE = ZoneInfo("America/Los_Angeles")

def assignment(key, due=None):
    return Assignment(key, "Course", key, "unknown", due)


def test_manual_target_only_applies_to_missing_deadlines_and_preserves_originals():
    a, b = assignment("missing"), assignment("dated", datetime(2026,11,14,tzinfo=ZONE))
    tasks = resolve_tasks([a,b], {"missing":60,"dated":60},
                          {"missing":DeadlineChoice(date(2026,11,12)), "dated":DeadlineChoice(date(2026,11,19))}, ZONE)
    assert tasks[0].due_at == datetime(2026,11,12,23,59,tzinfo=ZONE)
    assert tasks[1].due_at == b.due_at and a.due_at is None


def test_manual_deadline_generates_sessions_with_existing_scheduler():
    tasks = resolve_tasks([assignment("x")], {"x":90}, {"x":DeadlineChoice(date(2026,11,12))}, ZONE)
    start = datetime(2026,11,9,18,tzinfo=ZONE)
    end = datetime(2026,11,9,20,tzinfo=ZONE)
    result = build_schedule(tasks, [AvailabilityPeriod(start,end)], SchedulingPreferences(start,ZONE,60,120))
    assert sum(s.duration_minutes for s in result.sessions) == 90
    assert not result.unscheduled_work


def test_no_manual_deadline_leaves_all_minutes_explicitly_unscheduled():
    tasks = resolve_tasks([assignment("x")], {"x":90}, {}, ZONE)
    start = datetime(2026,11,9,18,tzinfo=ZONE)
    result = build_schedule(tasks, [], SchedulingPreferences(start,ZONE,60,120))
    assert not result.sessions
    assert result.unscheduled_work[0].reason == "missing_deadline"
    assert result.unscheduled_work[0].remaining_minutes == 90


def test_ambiguous_manual_time_is_rejected_instead_of_guessing():
    with pytest.raises(ValueError):
        resolve_tasks([assignment("x")], {"x":60}, {"x":DeadlineChoice(date(2026,11,1),"01:30")}, ZONE)
