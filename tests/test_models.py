"""Tests for the planner's internal assignment representation."""

from datetime import datetime, timezone

import pytest

from workload_planner.models import Assignment


def test_assignment_stores_valid_values() -> None:
    """A valid assignment should preserve all of its supplied information."""
    deadline = datetime(2026, 9, 15, 23, 59, tzinfo=timezone.utc)

    assignment = Assignment(
        assignment_id="assignment-1",
        course="CS 101",
        title="Programming Exercise 1",
        assignment_type="programming",
        due_at=deadline,
        points_possible=50.0,
        description="Create a small Python program.",
    )

    assert assignment.assignment_id == "assignment-1"
    assert assignment.course == "CS 101"
    assert assignment.title == "Programming Exercise 1"
    assert assignment.assignment_type == "programming"
    assert assignment.due_at == deadline
    assert assignment.points_possible == 50.0
    assert assignment.description == "Create a small Python program."


def test_assignment_allows_missing_optional_values() -> None:
    """An assignment may have no deadline, point value, or description."""
    assignment = Assignment(
        assignment_id="assignment-2",
        course="HIST 201",
        title="Optional Reading",
        assignment_type="reading",
        due_at=None,
    )

    assert assignment.due_at is None
    assert assignment.points_possible is None
    assert assignment.description == ""


@pytest.mark.parametrize(
    "field_name",
    ["assignment_id", "course", "title", "assignment_type"],
)
def test_assignment_rejects_blank_required_text(field_name: str) -> None:
    """Required text fields should reject values containing only whitespace."""
    values = {
        "assignment_id": "assignment-3",
        "course": "ENG 101",
        "title": "Essay Draft",
        "assignment_type": "essay",
        "due_at": None,
    }
    values[field_name] = "   "

    with pytest.raises(ValueError, match=field_name):
        Assignment(**values)


@pytest.mark.parametrize(
    "field_name",
    ["assignment_id", "course", "title", "assignment_type"],
)
def test_assignment_rejects_non_text_required_fields(field_name: str) -> None:
    """Required text fields should reject values that are not strings."""
    values = {
        "assignment_id": "assignment-3",
        "course": "ENG 101",
        "title": "Essay Draft",
        "assignment_type": "essay",
        "due_at": None,
    }
    values[field_name] = 123

    with pytest.raises(TypeError, match=field_name):
        Assignment(**values)


def test_assignment_rejects_negative_points() -> None:
    """A maximum point value cannot be less than zero."""
    with pytest.raises(ValueError, match="points_possible"):
        Assignment(
            assignment_id="assignment-4",
            course="MATH 101",
            title="Problem Set",
            assignment_type="homework",
            due_at=None,
            points_possible=-10.0,
        )


def test_assignment_rejects_non_numeric_points() -> None:
    """A point value should be a number when it is supplied."""
    with pytest.raises(TypeError, match="points_possible"):
        Assignment(
            assignment_id="assignment-4",
            course="MATH 101",
            title="Problem Set",
            assignment_type="homework",
            due_at=None,
            points_possible="ten",
        )


def test_assignment_rejects_deadline_without_timezone() -> None:
    """A deadline should include its timezone or UTC offset."""
    deadline_without_timezone = datetime(2026, 9, 15, 23, 59)

    with pytest.raises(ValueError, match="due_at"):
        Assignment(
            assignment_id="assignment-5",
            course="CS 101",
            title="Programming Exercise 2",
            assignment_type="programming",
            due_at=deadline_without_timezone,
        )


def test_assignment_rejects_non_datetime_deadline() -> None:
    """A supplied deadline should already be converted to a datetime."""
    with pytest.raises(TypeError, match="due_at"):
        Assignment(
            assignment_id="assignment-5",
            course="CS 101",
            title="Programming Exercise 2",
            assignment_type="programming",
            due_at="2026-09-15T23:59:00-07:00",
        )


def test_assignment_rejects_non_text_description() -> None:
    """A supplied description should be text."""
    with pytest.raises(TypeError, match="description"):
        Assignment(
            assignment_id="assignment-6",
            course="BIOL 101",
            title="Lab Notes",
            assignment_type="homework",
            due_at=None,
            description=123,
        )
