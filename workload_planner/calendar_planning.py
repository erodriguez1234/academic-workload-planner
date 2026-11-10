"""Fit new study work around busy time and retain previously booked sessions."""

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from collections.abc import Iterator, Sequence

from workload_planner.scheduler import build_schedule
from workload_planner.scheduling_models import (
    AvailabilityPeriod, ScheduleResult, SchedulingPreferences, SchedulingTask, StudySession,
)

UTC = timezone.utc


@dataclass(frozen=True)
class BusyPeriod:
    """Busy intervals may have second precision, unlike whole-minute study slots."""

    start_at: datetime
    end_at: datetime

    def __post_init__(self) -> None:
        for value in (self.start_at, self.end_at):
            if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
                raise ValueError("busy times must be timezone-aware datetimes")
        if self.end_at.astimezone(UTC) <= self.start_at.astimezone(UTC):
            raise ValueError("busy intervals must have positive duration")


def subtract_busy(
    availability: Sequence[AvailabilityPeriod], busy: Sequence[BusyPeriod],
) -> tuple[AvailabilityPeriod, ...]:
    """Remove busy time in UTC; conservatively round free slots inward to minutes."""
    blocked = sorted((b.start_at.astimezone(UTC), b.end_at.astimezone(UTC)) for b in busy)
    free: list[AvailabilityPeriod] = []

    def add(start: datetime, end: datetime) -> None:
        rounded = start.replace(second=0, microsecond=0)
        if rounded < start:
            rounded += timedelta(minutes=1)
        end = end.replace(second=0, microsecond=0)
        if rounded < end:
            free.append(AvailabilityPeriod(rounded, end))

    for period in availability:
        cursor, end = period.start_at.astimezone(UTC), period.end_at.astimezone(UTC)
        for busy_start, busy_end in blocked:
            if busy_end <= cursor:
                continue
            if busy_start >= end:
                break
            if busy_start > cursor:
                add(cursor, min(busy_start, end))
            cursor = max(cursor, busy_end)
            if cursor >= end:
                break
        if cursor < end:
            add(cursor, end)
    return tuple(free)


def _day_parts(start: datetime, end: datetime, settings: SchedulingPreferences) -> Iterator[tuple[date, datetime, datetime]]:
    start, end = start.astimezone(UTC), end.astimezone(UTC)
    while start < end:
        day = start.astimezone(settings.student_timezone).date()
        midnight = datetime.combine(day + timedelta(days=1), time.min, tzinfo=settings.student_timezone).astimezone(UTC)
        stop = min(end, midnight)
        yield day, start, stop
        start = stop


def build_calendar_schedule(
    tasks: Sequence[SchedulingTask], availability: Sequence[AvailabilityPeriod],
    settings: SchedulingPreferences, busy: Sequence[BusyPeriod], booked: Sequence[StudySession],
) -> ScheduleResult:
    """Credit existing bookings, then use the unchanged scheduler for remaining work.

    Already booked sessions stay in place, including sessions outside the new
    availability horizon. They consume daily study budgets. New sessions stay
    within availability minus busy time. Changed bookings require manual review.
    """
    by_id = {task.assignment_id: task for task in tasks}
    credited: list[StudySession] = []
    minutes = dict.fromkeys(by_id, 0)
    ordered_bookings = sorted(booked, key=lambda s: s.start_at.astimezone(UTC))
    for previous, current in zip(ordered_bookings, ordered_bookings[1:]):
        if current.start_at.astimezone(UTC) < previous.end_at.astimezone(UTC):
            raise ValueError("The existing planner sessions overlap; review them before generating more work.")
    for session in ordered_bookings:
        if session.assignment_id not in by_id:
            continue
        task = by_id[session.assignment_id]
        if session.start_at.astimezone(UTC) < settings.planning_start.astimezone(UTC) or task.due_at is None or session.end_at.astimezone(UTC) > task.due_at.astimezone(UTC):
            raise ValueError("An existing planner session is in progress or no longer fits its deadline; review it before replanning.")
        minutes[session.assignment_id] += session.duration_minutes
        if minutes[session.assignment_id] > task.required_minutes:
            raise ValueError("The existing planner minutes exceed the adjusted assignment minutes; review the workload first.")
        credited.append(session)
    remaining = [SchedulingTask(t.assignment_id, t.required_minutes - minutes[t.assignment_id], t.due_at) for t in tasks if t.required_minutes > minutes[t.assignment_id]]
    blocked = [*busy, *(BusyPeriod(s.start_at, s.end_at) for s in booked)]
    free = subtract_busy(availability, blocked)
    used_by_day = {}
    for session in booked:
        for day, start, end in _day_parts(session.start_at, session.end_at, settings):
            used_by_day[day] = used_by_day.get(day, 0) + int((end - start).total_seconds() // 60)
    # The core scheduler's cap remains unchanged; reduce the day's new capacity
    # first so existing study bookings also consume that cap.
    budget_by_day = {}
    limited = []
    for period in sorted(free, key=lambda p: p.start_at):
        start = max(period.start_at.astimezone(UTC), settings.planning_start.astimezone(UTC))
        for day, start, end in _day_parts(start, period.end_at, settings):
            budget = budget_by_day.setdefault(day, max(0, settings.daily_study_limit_minutes - used_by_day.get(day, 0)))
            usable = min(budget, int((end - start).total_seconds() // 60))
            if usable:
                limited.append(AvailabilityPeriod(start, start + timedelta(minutes=usable)))
                budget_by_day[day] -= usable
    new = build_schedule(remaining, limited, settings)
    return ScheduleResult(tuple(tasks), tuple(sorted((*credited, *new.sessions), key=lambda s: s.start_at.astimezone(UTC))), new.unscheduled_work)
