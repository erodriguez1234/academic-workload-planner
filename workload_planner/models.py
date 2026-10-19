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
