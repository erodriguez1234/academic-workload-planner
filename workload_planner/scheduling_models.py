"""Validated scheduling inputs and outputs; no placement algorithm.

Policies implemented by scheduler.build_schedule:
- Use an explicit planning start and the student's ZoneInfo for daily limits.
- Leave missing deadlines and deadlines <= planning start fully unscheduled.
- Order tasks by deadline in UTC, then assignment_id; reject duplicate IDs.
- Reject overlapping availability (touching endpoints are allowed).
- Allow availability across midnight; split sessions at student-local midnight.
- Use whole active minutes, clip availability to planning start/deadline, and
  enforce availability, non-overlap, session caps, and daily caps in the scheduler.
- Ending exactly at a deadline is allowed. Greedy failure is not a proof that
  no feasible schedule exists.

These models validate individual values and per-task minute accounting only.
scheduler.build_schedule applies contextual scheduling constraints during placement.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Literal
from zoneinfo import ZoneInfo


UnscheduledReason = Literal[
    "missing_deadline", "deadline_not_after_start", "unplaced_by_greedy"
]


def _validate_text(value: str, field_name: str) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string")
    if not value.strip():
        raise ValueError(f"{field_name} cannot be blank")


def _validate_minutes(value: int, field_name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{field_name} must be an integer")
    if value <= 0:
        raise ValueError(f"{field_name} must be greater than zero")


def _validate_datetime(value: datetime, field_name: str) -> None:
    if not isinstance(value, datetime):
        raise TypeError(f"{field_name} must be a datetime")
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must include timezone information")


def _elapsed_minutes(start_at: datetime, end_at: datetime) -> int:
    """Validate the interval and count actual elapsed minutes, including DST."""
    _validate_datetime(start_at, "start_at")
    _validate_datetime(end_at, "end_at")
    elapsed = end_at.astimezone(timezone.utc) - start_at.astimezone(timezone.utc)
    seconds = elapsed.total_seconds()
    if seconds <= 0 or seconds % 60 != 0:
        raise ValueError("end_at must be after start_at by positive whole minutes")
    return int(seconds // 60)


@dataclass(frozen=True)
class AvailabilityPeriod:
    """A dated window; crossing midnight is allowed. No recurrence expansion."""

    start_at: datetime
    end_at: datetime

    def __post_init__(self) -> None:
        _elapsed_minutes(self.start_at, self.end_at)

    @property
    def duration_minutes(self) -> int:
        return _elapsed_minutes(self.start_at, self.end_at)


@dataclass(frozen=True)
class SchedulingPreferences:
    """Explicit planning context and positive whole-minute study limits.

    A session cap may exceed the daily cap; the scheduler must respect both.
    Supply ZoneInfo("America/Los_Angeles"), for example, to identify local days.
    """

    planning_start: datetime
    student_timezone: ZoneInfo
    max_session_minutes: int
    daily_study_limit_minutes: int

    def __post_init__(self) -> None:
        _validate_datetime(self.planning_start, "planning_start")
        if not isinstance(self.student_timezone, ZoneInfo):
            raise TypeError("student_timezone must be a ZoneInfo")
        _validate_minutes(self.max_session_minutes, "max_session_minutes")
        _validate_minutes(self.daily_study_limit_minutes, "daily_study_limit_minutes")


@dataclass(frozen=True)
class SchedulingTask:
    """Requested active work, independent of estimation method or metadata.

    Missing/past deadlines are valid data; eligibility is a scheduler decision.
    """

    assignment_id: str
    required_minutes: int
    due_at: datetime | None

    def __post_init__(self) -> None:
        _validate_text(self.assignment_id, "assignment_id")
        _validate_minutes(self.required_minutes, "required_minutes")
        if self.due_at is not None:
            _validate_datetime(self.due_at, "due_at")


@dataclass(frozen=True)
class StudySession:
    """A positive work interval; duration is derived to avoid conflicting fields."""

    assignment_id: str
    start_at: datetime
    end_at: datetime

    def __post_init__(self) -> None:
        _validate_text(self.assignment_id, "assignment_id")
        _elapsed_minutes(self.start_at, self.end_at)

    @property
    def duration_minutes(self) -> int:
        return _elapsed_minutes(self.start_at, self.end_at)


@dataclass(frozen=True)
class UnscheduledWork:
    """Remaining active minutes, a stable reason code, and a readable message."""

    assignment_id: str
    remaining_minutes: int
    reason: UnscheduledReason

    def __post_init__(self) -> None:
        _validate_text(self.assignment_id, "assignment_id")
        _validate_minutes(self.remaining_minutes, "remaining_minutes")
        _validate_text(self.reason, "reason")
        if self.reason not in (
            "missing_deadline", "deadline_not_after_start", "unplaced_by_greedy"
        ):
            raise ValueError("reason must be a supported unscheduled-work code")

    @property
    def message(self) -> str:
        """Describe the unplaced work without claiming that it is impossible.

        Derived from the validated fields rather than stored separately, so the
        explanation stays consistent with the assignment, minutes, and reason.
        """
        explanations = {
            "missing_deadline": "no deadline was supplied",
            "deadline_not_after_start": "the deadline is at or before the planning start",
            "unplaced_by_greedy": (
                "the greedy scheduler left this work unplaced under the supplied "
                "availability, deadlines, and study limits"
            ),
        }
        return (
            f"Could not schedule {self.remaining_minutes} active working minutes "
            f"for assignment '{self.assignment_id}': {explanations[self.reason]}."
        )


@dataclass(frozen=True)
class ScheduleResult:
    """An accounted result, not a certificate of schedule feasibility.

    Each unique task must have scheduled minutes + remaining minutes equal to
    required minutes. At most one remainder record is allowed per task. Tuples
    prevent collection edits after validation; empty results are valid.
    Availability, deadlines, limits, and overlaps need contextual validation in
    scheduler.build_schedule, which also determines the correct reason code.
    """

    tasks: tuple[SchedulingTask, ...]
    sessions: tuple[StudySession, ...]
    unscheduled_work: tuple[UnscheduledWork, ...]

    def __post_init__(self) -> None:
        for name, values, model in (
            ("tasks", self.tasks, SchedulingTask),
            ("sessions", self.sessions, StudySession),
            ("unscheduled_work", self.unscheduled_work, UnscheduledWork),
        ):
            if not isinstance(values, tuple) or not all(
                isinstance(value, model) for value in values
            ):
                raise TypeError(f"{name} must be a tuple of {model.__name__} objects")

        requested: dict[str, int] = {}
        for task in self.tasks:
            if task.assignment_id in requested:
                raise ValueError(f"duplicate task assignment_id: {task.assignment_id}")
            requested[task.assignment_id] = task.required_minutes

        accounted = dict.fromkeys(requested, 0)
        for session in self.sessions:
            if session.assignment_id not in requested:
                raise ValueError(f"unknown session assignment_id: {session.assignment_id}")
            accounted[session.assignment_id] += session.duration_minutes

        remaining_ids: set[str] = set()
        for work in self.unscheduled_work:
            if work.assignment_id not in requested:
                raise ValueError(f"unknown unscheduled assignment_id: {work.assignment_id}")
            if work.assignment_id in remaining_ids:
                raise ValueError(f"duplicate unscheduled assignment_id: {work.assignment_id}")
            remaining_ids.add(work.assignment_id)
            accounted[work.assignment_id] += work.remaining_minutes

        for assignment_id, minutes in requested.items():
            if accounted[assignment_id] != minutes:
                raise ValueError(
                    f"minute accounting for {assignment_id}: requested {minutes}, "
                    f"accounted for {accounted[assignment_id]}"
                )
