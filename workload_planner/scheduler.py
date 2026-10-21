"""Deterministic earliest-deadline-first scheduling of active working minutes.

This greedy baseline fills the earliest available time without backtracking.
It does not optimize spacing, insert breaks, or prove infeasibility when work
remains. All time arithmetic uses UTC; sessions and daily limits use the
student's timezone. Inputs are not modified and no computer clock is read.
"""

from collections.abc import Sequence
from datetime import date, datetime, time, timedelta, timezone

from workload_planner.scheduling_models import (
    AvailabilityPeriod,
    ScheduleResult,
    SchedulingPreferences,
    SchedulingTask,
    StudySession,
    UnscheduledWork,
)


def _prepare_slots(
    availability: Sequence[AvailabilityPeriod],
    preferences: SchedulingPreferences,
) -> list[tuple[datetime, datetime]]:
    """Sort UTC windows, reject overlaps, and split them at local midnight.

    Each returned pair is a free-time window belonging to one student-local
    day. Touching endpoints are allowed. Reject overlaps before clipping, so
    invalid input is reported even if the overlap precedes planning_start.
    """
    periods = sorted(
        (period.start_at.astimezone(timezone.utc),
         period.end_at.astimezone(timezone.utc))
        for period in availability
    )
    for previous, current in zip(periods, periods[1:]):
        if current[0] < previous[1]:
            raise ValueError("availability periods cannot overlap")

    planning_start = preferences.planning_start.astimezone(timezone.utc)
    zone = preferences.student_timezone
    slots: list[tuple[datetime, datetime]] = []
    for start, end in periods:
        cursor = max(start, planning_start)
        while cursor < end:
            next_date = cursor.astimezone(zone).date() + timedelta(days=1)
            midnight = datetime.combine(next_date, time.min, tzinfo=zone)
            slot_end = min(end, midnight.astimezone(timezone.utc))
            slots.append((cursor, slot_end))
            cursor = slot_end
    return slots


def build_schedule(
    tasks: Sequence[SchedulingTask],
    availability: Sequence[AvailabilityPeriod],
    preferences: SchedulingPreferences,
) -> ScheduleResult:
    """Place requested work by deadline, breaking ties by assignment ID.

    Accept lists or tuples of validated models. Task order in the result is
    preserved; sessions are chronological and expressed in student_timezone.
    Duplicate task IDs and overlapping availability raise ValueError.

    Missing deadlines and deadlines <= planning_start remain fully unscheduled
    with explicit reasons. Other remaining minutes use unplaced_by_greedy.
    Sessions can end exactly at deadlines. Fractional-minute capacity is rounded
    down, never past a deadline. Sessions may be adjacent, with no break inserted.
    Daily limits count only sessions produced by this call; existing work/busy
    events must be handled separately in a later integration.
    """
    requested = tuple(tasks)
    task_ids: set[str] = set()
    for task in requested:
        if task.assignment_id in task_ids:
            raise ValueError(f"duplicate task assignment_id: {task.assignment_id}")
        task_ids.add(task.assignment_id)

    slots = _prepare_slots(availability, preferences)
    planning_start = preferences.planning_start.astimezone(timezone.utc)
    zone = preferences.student_timezone
    unscheduled: list[UnscheduledWork] = []
    eligible: list[tuple[datetime, SchedulingTask]] = []
    for task in requested:
        if task.due_at is None:
            unscheduled.append(UnscheduledWork(
                task.assignment_id, task.required_minutes, "missing_deadline"
            ))
        elif task.due_at.astimezone(timezone.utc) <= planning_start:
            unscheduled.append(UnscheduledWork(
                task.assignment_id, task.required_minutes, "deadline_not_after_start"
            ))
        else:
            eligible.append((task.due_at.astimezone(timezone.utc), task))

    sessions: list[StudySession] = []
    minutes_by_day: dict[date, int] = {}
    for deadline, task in sorted(eligible, key=lambda item: (item[0], item[1].assignment_id)):
        remaining = task.required_minutes
        for index, (cursor, slot_end) in enumerate(slots):
            if remaining == 0 or cursor >= deadline:
                break
            usable_end = min(slot_end, deadline)
            local_day = cursor.astimezone(zone).date()
            while remaining > 0:
                available_minutes = int((usable_end - cursor).total_seconds() // 60)
                daily_remaining = (
                    preferences.daily_study_limit_minutes - minutes_by_day.get(local_day, 0)
                )
                minutes = min(
                    remaining,
                    preferences.max_session_minutes,
                    available_minutes,
                    daily_remaining,
                )
                if minutes <= 0:
                    break
                session_end = cursor + timedelta(minutes=minutes)
                sessions.append(StudySession(
                    task.assignment_id,
                    cursor.astimezone(zone),
                    session_end.astimezone(zone),
                ))
                remaining -= minutes
                minutes_by_day[local_day] = minutes_by_day.get(local_day, 0) + minutes
                # Consume only the placed part; later tasks can use the rest.
                cursor = session_end
                slots[index] = (cursor, slot_end)
            # Moving to the next slot handles gaps, full days, and midnight.
        if remaining > 0:
            unscheduled.append(UnscheduledWork(
                task.assignment_id, remaining, "unplaced_by_greedy"
            ))

    sessions.sort(key=lambda session: session.start_at.astimezone(timezone.utc))
    return ScheduleResult(requested, tuple(sessions), tuple(unscheduled))
