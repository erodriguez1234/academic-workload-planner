"""Behavior tests for provisional assignment-type duration estimates."""

from dataclasses import asdict, replace
from datetime import datetime, timezone
from pathlib import Path

import pytest

from workload_planner.estimator import estimate_duration
from workload_planner.loaders import load_assignments
from workload_planner.models import Assignment, DurationEstimate


@pytest.fixture
def assignment() -> Assignment:
    return Assignment("task-1", "CS 101", "Practice", "quiz", due_at=None)


@pytest.mark.parametrize(
    "assignment_type, minutes",
    [("quiz", 30), ("discussion", 45), ("reading", 60),
     ("homework", 90), ("essay", 180), ("programming", 180)],
)
def test_supported_types_use_documented_defaults(
    assignment: Assignment, assignment_type: str, minutes: int
) -> None:
    assignment = replace(assignment, assignment_type=assignment_type)

    estimate = estimate_duration(assignment)

    assert isinstance(estimate, DurationEstimate)
    assert estimate.assignment_id == assignment.assignment_id
    assert estimate.estimated_minutes == minutes
    assert estimate.method == "rule_based_v1"
    assert assignment_type in estimate.explanation
    assert str(minutes) in estimate.explanation
    assert "default" in estimate.explanation.lower()
    assert "not personalized" in estimate.explanation.lower()


@pytest.mark.parametrize("assignment_type", ["Quiz", "QUIZ", "  Quiz\t"])
def test_type_normalization_preserves_assignment(
    assignment: Assignment, assignment_type: str
) -> None:
    assignment = replace(assignment, assignment_type=assignment_type)
    original = asdict(assignment)

    estimate = estimate_duration(assignment)

    assert estimate.estimated_minutes == 30
    assert asdict(assignment) == original


@pytest.mark.parametrize("assignment_type", ["presentation", "  LAB  "])
def test_unknown_type_has_explicit_fallback(
    assignment: Assignment, assignment_type: str
) -> None:
    assignment = replace(assignment, assignment_type=assignment_type)

    estimate = estimate_duration(assignment)

    assert estimate.estimated_minutes == 90
    assert assignment_type.strip().lower() in estimate.explanation
    assert "fallback" in estimate.explanation.lower()
    assert "unrecognized" in estimate.explanation.lower()
    assert estimate.method == "rule_based_v1"


def test_estimation_is_repeatable_and_does_not_mutate(assignment: Assignment) -> None:
    original = asdict(assignment)

    assert estimate_duration(assignment) == estimate_duration(assignment)
    assert asdict(assignment) == original


def test_only_assignment_type_affects_duration(assignment: Assignment) -> None:
    changed = replace(
        assignment,
        course="BIOL 201",
        title="A different title",
        description="A long description does not automatically mean more work.",
        points_possible=200,
        due_at=datetime(2026, 10, 12, tzinfo=timezone.utc),
    )

    assert estimate_duration(changed).estimated_minutes == 30
    assert estimate_duration(assignment).estimated_minutes == 30


def test_sample_assignments_can_be_loaded_and_estimated() -> None:
    path = Path(__file__).resolve().parents[1] / "sample_data" / "assignments.json"
    assignments = load_assignments(path)

    estimates = [estimate_duration(assignment) for assignment in assignments]

    assert {estimate.assignment_id: estimate.estimated_minutes for estimate in estimates} == {
        "sample-quiz-1": 30,
        "sample-essay-1": 180,
        "sample-reading-1": 60,
        "sample-programming-1": 180,
    }
