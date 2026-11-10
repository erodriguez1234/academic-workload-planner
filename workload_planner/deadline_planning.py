"""Resolve student planning targets and schedule weekly assumptions at lower priority."""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from workload_planner.availability import localize_datetime
from workload_planner.calendar_planning import BusyPeriod, build_calendar_schedule
from workload_planner.models import Assignment
from workload_planner.scheduling_models import AvailabilityPeriod, ScheduleResult, SchedulingPreferences, SchedulingTask, StudySession, UnscheduledWork


@dataclass(frozen=True)
class DeadlineChoice:
    mode: str
    day: date
    clock: str = "23:59"


def resolve_tasks(
    assignments: Sequence[Assignment], minutes: dict[str, int], choices: dict[str, DeadlineChoice], zone: ZoneInfo,
    *, horizon_end: datetime | None = None,
) -> tuple[list[SchedulingTask], dict[str, tuple[datetime, datetime]]]:
    """Keep Canvas dates intact; assumptions create separate scheduling inputs."""
    tasks, weeks = [], {}
    for assignment in assignments:
        due = assignment.due_at
        choice = choices.get(assignment.assignment_id)
        if due is None and choice is not None:
            if choice.mode == "manual":
                due = localize_datetime(datetime.combine(choice.day, time.fromisoformat(choice.clock)), zone)
            elif choice.mode == "week":
                if horizon_end is None:
                    raise ValueError("Enter a planning horizon for work without a real deadline.")
                monday = choice.day - timedelta(days=choice.day.weekday())
                start = localize_datetime(datetime.combine(monday, time.min), zone)
                end = localize_datetime(datetime.combine(monday + timedelta(days=7), time.min), zone)
                due = horizon_end  # A planning cutoff, never a Canvas/student due date.
                weeks[assignment.assignment_id] = (start, end)
            else:
                raise ValueError("Choose a manual planning deadline or a reference week.")
        tasks.append(SchedulingTask(assignment.assignment_id, minutes[assignment.assignment_id], due))
    return tasks, weeks


def build_reviewed_schedule(
    tasks: Sequence[SchedulingTask], availability: Sequence[AvailabilityPeriod], settings: SchedulingPreferences,
    weeks: dict[str, tuple[datetime, datetime]], *, busy: Sequence[BusyPeriod] = (), booked: Sequence[StudySession] = (),
    assigned_weeks: dict[str, date] | None = None,
) -> ScheduleResult:
    """Reserve dated work first, then fit weekly work in remaining time/capacity.

    Dated work reserves capacity first. Weekly work waits for the last dated-work
    day of its reference week, and may spill later up to the planning cutoff.
    """
    normal = [task for task in tasks if task.assignment_id not in weeks]
    first = build_calendar_schedule(normal, availability, settings, busy, booked)
    sessions, remaining = list(first.sessions), list(first.unscheduled_work)
    carried = list(booked)
    carried.extend(s for s in first.sessions if s not in carried)
    for task in sorted((t for t in tasks if t.assignment_id in weeks), key=lambda t: (weeks[t.assignment_id][0], t.assignment_id)):
        start, end = weeks[task.assignment_id]
        related = []
        for dated in normal:
            if dated.due_at is None:
                continue
            mapped = (assigned_weeks or {}).get(dated.assignment_id)
            belongs = mapped == start.date() if mapped is not None else start <= dated.due_at < end
            if belongs:
                related.append(dated)
        related_ids = {t.assignment_id for t in related}
        waiting = any(w.assignment_id in related_ids for w in first.unscheduled_work)
        due_days = [localize_datetime(datetime.combine(t.due_at.astimezone(settings.student_timezone).date(), time.min), settings.student_timezone) for t in related if t.due_at is not None]
        release = max([start, *due_days, *(s.end_at for s in first.sessions if s.assignment_id in related_ids)], key=lambda d: d.astimezone(timezone.utc))
        if any(s.assignment_id == task.assignment_id and (s.start_at.astimezone(timezone.utc) < release.astimezone(timezone.utc) or waiting) for s in booked):
            raise ValueError("An existing planner session is earlier than the reviewed priority allows; review it before replanning.")
        if waiting:
            remaining.append(UnscheduledWork(task.assignment_id, task.required_minutes, "unplaced_by_greedy"))
            continue
        clipped = []
        for period in availability:
            left = max(period.start_at.astimezone(timezone.utc), release.astimezone(timezone.utc))
            right = min(period.end_at.astimezone(timezone.utc), task.due_at.astimezone(timezone.utc))
            if left < right:
                clipped.append(AvailabilityPeriod(left, right))
        later = build_calendar_schedule([task], clipped, settings, busy, carried)
        sessions.extend(later.sessions)
        remaining.extend(later.unscheduled_work)
        carried.extend(s for s in later.sessions if s not in carried)
    return ScheduleResult(tuple(tasks), tuple(sorted(sessions, key=lambda s: s.start_at.astimezone(timezone.utc))), tuple(remaining))
