"""Internal data representations for the planner."""

from dataclasses import dataclass
from datetime import datetime


@dataclass
class Assignment:
    """A normalized academic assignment used throughout the planner."""

    assignment_id: str
    course: str
    title: str
    assignment_type: str
    due_at: datetime | None
    points_possible: float | None = None
    description: str = ""

    def __post_init__(self) -> None:
        """Validate values that every assignment must satisfy."""
        required_text = {
            "assignment_id": self.assignment_id,
            "course": self.course,
            "title": self.title,
            "assignment_type": self.assignment_type,
        }

        for field_name, value in required_text.items():
            if not isinstance(value, str):
                raise TypeError(f"{field_name} must be a string")
            if not value.strip():
                raise ValueError(f"{field_name} cannot be blank")

        if self.points_possible is not None:
            if isinstance(self.points_possible, bool) or not isinstance(
                self.points_possible, (int, float)
            ):
                raise TypeError("points_possible must be a number or None")
            if self.points_possible < 0:
                raise ValueError("points_possible cannot be negative")

        if self.due_at is not None:
            if not isinstance(self.due_at, datetime):
                raise TypeError("due_at must be a datetime or None")
            if self.due_at.tzinfo is None or self.due_at.utcoffset() is None:
                raise ValueError("due_at must include timezone information")

        if not isinstance(self.description, str):
            raise TypeError("description must be a string")


@dataclass
class DurationEstimate:
    """An explained prediction of active working minutes for an assignment.

    Includes understanding instructions, doing the work, and reviewing it;
    excludes breaks and waiting time. Validation occurs at construction.
    """

    assignment_id: str
    estimated_minutes: int
    method: str
    explanation: str

    def __post_init__(self) -> None:
        """Require positive whole minutes and meaningful identifying text."""
        required_text = {
            "assignment_id": self.assignment_id,
            "method": self.method,
            "explanation": self.explanation,
        }
        for field_name, value in required_text.items():
            if not isinstance(value, str):
                raise TypeError(f"{field_name} must be a string")
            if not value.strip():
                raise ValueError(f"{field_name} cannot be blank")

        # bool is a subclass of int, but True/False are not valid durations.
        if isinstance(self.estimated_minutes, bool) or not isinstance(
            self.estimated_minutes, int
        ):
            raise TypeError("estimated_minutes must be an integer")
        if self.estimated_minutes <= 0:
            raise ValueError("estimated_minutes must be greater than zero")
