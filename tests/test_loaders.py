"""Tests for loading and validating assignment data."""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from workload_planner.loaders import load_assignments
from workload_planner.models import Assignment


@pytest.fixture
def valid_record() -> dict[str, object]:
    """Give each test a fresh assignment record in the JSON input format."""
    return {
        "assignment_id": "quiz-1",
        "course": "BIOL 101",
        "title": "Cell Biology Quiz",
        "assignment_type": "quiz",
        "due_at": "2026-10-12T18:00:00-07:00",
        "points_possible": 20.0,
        "description": "Review cell structures and complete the quiz.",
    }


def write_json(tmp_path: Path, data: object) -> Path:
    """Write test data to a temporary JSON file and return its path."""
    path = tmp_path / "assignments.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def test_load_assignments_returns_models(
    tmp_path: Path, valid_record: dict[str, object]
) -> None:
    """Load several records, preserving their information and input order."""
    second_record = {
        **valid_record,
        "assignment_id": "quiz-2",
        "title": "Genetics Quiz",
    }
    path = write_json(tmp_path, [valid_record, second_record])

    assignments = load_assignments(path)

    assert isinstance(assignments, list)
    assert len(assignments) == 2
    assert all(isinstance(assignment, Assignment) for assignment in assignments)
    assert [assignment.assignment_id for assignment in assignments] == [
        "quiz-1", "quiz-2"
    ]
    assert assignments[0].course == "BIOL 101"
    assert assignments[0].title == "Cell Biology Quiz"
    assert assignments[0].assignment_type == "quiz"
    assert assignments[0].points_possible == 20.0
    assert assignments[0].description == valid_record["description"]
    assert assignments[1].title == "Genetics Quiz"


@pytest.mark.parametrize(
    "deadline_text, expected",
    [
        (
            "2026-10-12T18:00:00-07:00",
            datetime(2026, 10, 12, 18, tzinfo=timezone(timedelta(hours=-7))),
        ),
        ("2026-10-13T01:00:00Z", datetime(2026, 10, 13, 1, tzinfo=timezone.utc)),
    ],
)
def test_load_assignments_converts_deadlines(
    tmp_path: Path,
    valid_record: dict[str, object],
    deadline_text: str,
    expected: datetime,
) -> None:
    """Offset and UTC strings should become aware datetimes for the right instant."""
    valid_record["due_at"] = deadline_text
    path = write_json(tmp_path, [valid_record])

    deadline = load_assignments(path)[0].due_at

    assert isinstance(deadline, datetime)
    assert deadline.utcoffset() is not None
    assert deadline == expected


def test_load_assignments_accepts_null_values(
    tmp_path: Path, valid_record: dict[str, object]
) -> None:
    """JSON null should become None for deadlines and points."""
    valid_record["due_at"] = None
    valid_record["points_possible"] = None
    path = write_json(tmp_path, [valid_record])

    assignment = load_assignments(path)[0]

    assert assignment.due_at is None
    assert assignment.points_possible is None


def test_load_assignments_uses_optional_defaults(
    tmp_path: Path, valid_record: dict[str, object]
) -> None:
    """Omitted points and description should use the model's defaults."""
    del valid_record["points_possible"]
    del valid_record["description"]
    path = write_json(tmp_path, [valid_record])

    assignment = load_assignments(path)[0]

    assert assignment.points_possible is None
    assert assignment.description == ""


def test_load_assignments_accepts_empty_list(tmp_path: Path) -> None:
    path = write_json(tmp_path, [])

    assert load_assignments(path) == []


@pytest.mark.parametrize("contents", ["", '[{"title": "Quiz"}'])
def test_load_assignments_reports_invalid_json(tmp_path: Path, contents: str) -> None:
    """An empty file or broken JSON should identify the file and format problem."""
    path = tmp_path / "broken.json"
    path.write_text(contents, encoding="utf-8")

    with pytest.raises(ValueError) as error:
        load_assignments(path)

    assert "broken.json" in str(error.value)
    assert "JSON" in str(error.value)


@pytest.mark.parametrize("data", [{"title": "Quiz"}, None, "assignments", 42])
def test_load_assignments_requires_list(tmp_path: Path, data: object) -> None:
    path = write_json(tmp_path, data)

    with pytest.raises(ValueError, match="list"):
        load_assignments(path)


@pytest.mark.parametrize("record", ["quiz", None, 42, []])
def test_load_assignments_requires_object_records(tmp_path: Path, record: object) -> None:
    path = write_json(tmp_path, [record])

    with pytest.raises(ValueError) as error:
        load_assignments(path)

    assert "record 1" in str(error.value).lower()
    assert "object" in str(error.value).lower()


@pytest.mark.parametrize(
    "field_name", ["assignment_id", "course", "title", "assignment_type", "due_at"]
)
def test_load_assignments_reports_missing_required_fields(
    tmp_path: Path, valid_record: dict[str, object], field_name: str
) -> None:
    """A missing deadline field is an error; an explicit null is permitted."""
    del valid_record[field_name]
    path = write_json(tmp_path, [valid_record])

    with pytest.raises(ValueError) as error:
        load_assignments(path)

    assert "record 1" in str(error.value).lower()
    assert field_name in str(error.value)


@pytest.mark.parametrize(
    "deadline", ["next Tuesday", "2026-02-30T18:00:00-07:00", "2026-10-12T18:00:00", 123]
)
def test_load_assignments_reports_invalid_deadlines(
    tmp_path: Path, valid_record: dict[str, object], deadline: object
) -> None:
    """Reject unparseable dates, impossible dates, naive dates, and wrong types."""
    valid_record["due_at"] = deadline
    path = write_json(tmp_path, [valid_record])

    with pytest.raises(ValueError) as error:
        load_assignments(path)

    assert "record 1" in str(error.value).lower()
    assert "due_at" in str(error.value)


@pytest.mark.parametrize(
    "field_name, invalid_value",
    [("title", "   "), ("points_possible", -10.0), ("description", 123)],
)
def test_load_assignments_adds_context_to_model_errors(
    tmp_path: Path,
    valid_record: dict[str, object],
    field_name: str,
    invalid_value: object,
) -> None:
    """A bad second record should raise an error instead of returning partial data."""
    invalid_record = {**valid_record, "assignment_id": "quiz-2"}
    invalid_record[field_name] = invalid_value
    path = write_json(tmp_path, [valid_record, invalid_record])

    with pytest.raises(ValueError) as error:
        load_assignments(path)

    assert "record 2" in str(error.value).lower()
    assert field_name in str(error.value)


def test_load_assignments_reports_missing_file(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_assignments(tmp_path / "missing.json")
