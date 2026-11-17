"""Resolve manual planning deadlines without changing imported assignments."""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime, time
from zoneinfo import ZoneInfo

from workload_planner.availability import localize_datetime
from workload_planner.models import Assignment
from workload_planner.scheduling_models import SchedulingTask


@dataclass(frozen=True)
class DeadlineChoice:
    day: date
    clock: str = "23:59"


def resolve_tasks(
    assignments: Sequence[Assignment], minutes: dict[str, int], choices: dict[str, DeadlineChoice], zone: ZoneInfo,
) -> list[SchedulingTask]:
    """Real deadlines win; undated work needs an explicit manual choice."""
    tasks = []
    for assignment in assignments:
        due = assignment.due_at
        choice = choices.get(assignment.assignment_id)
        if due is None and choice is not None:
            due = localize_datetime(datetime.combine(choice.day, time.fromisoformat(choice.clock)), zone)
        tasks.append(SchedulingTask(assignment.assignment_id, minutes[assignment.assignment_id], due))
    return tasks
