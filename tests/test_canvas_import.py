"""Canvas normalization policies, using synthetic student records only."""

from copy import deepcopy
from datetime import datetime
from unittest.mock import Mock

import pytest

from workload_planner.canvas_client import CanvasClientError
from workload_planner.canvas_import import convert_assignment, import_courses
from workload_planner.estimator import estimate_duration

SITE = "https://canvas.example.edu"
COURSE = {"id": 42, "name": "Python course"}


@pytest.fixture
def record() -> dict:
    return {"id": 7, "course_id": 42, "name": "Essay programming quiz",
            "due_at": "2026-11-12T21:30:00-08:00", "points_possible": 10,
            "description": "<p>Instructions</p>", "submission_types": ["online_upload"],
            "submission": {"workflow_state": "unsubmitted", "submitted_at": None}}


def test_preserves_fields_effective_deadline_and_input(record: dict) -> None:
    record["all_dates"] = [{"due_at": "2026-11-01T00:00:00Z"}]
    before = deepcopy(record)
    item = convert_assignment(record, COURSE, SITE)
    a = item.assignment
    assert a.assignment_id == "canvas:canvas.example.edu:42:7"
    assert (a.course, a.title, a.points_possible) == (COURSE["name"], record["name"], 10)
    assert a.due_at == datetime.fromisoformat(record["due_at"])
    assert a.description == record["description"]
    assert record == before
    assert item.status == "Unsubmitted" and item.selected_by_default


def test_ids_survive_renames_and_do_not_collide_across_courses_or_sites(record: dict) -> None:
    first = convert_assignment(record, COURSE, SITE).assignment.assignment_id
    renamed = convert_assignment({**record, "name": "New title"}, {**COURSE, "name": "New course"}, SITE)
    assert renamed.assignment.assignment_id == first
    other = convert_assignment({**record, "course_id": 43}, {**COURSE, "id": 43}, SITE)
    assert other.assignment.assignment_id != first
    assert convert_assignment(record, COURSE, "https://other.example.edu").assignment.assignment_id != first


@pytest.mark.parametrize("types, expected", [
    (["online_quiz"], "quiz"), (["discussion_topic"], "discussion"),
    (["online_upload"], "unknown"), (["online_text_entry"], "unknown"),
    (["external_tool"], "unknown"), (["none"], "unknown"), ([], "unknown"),
    (["online_quiz", "online_upload"], "unknown"), (None, "unknown"),
])
def test_type_mapping_does_not_guess_from_title(record: dict, types: object, expected: str) -> None:
    item = convert_assignment({**record, "submission_types": types}, COURSE, SITE)
    assert item.assignment.assignment_type == expected
    if expected == "unknown":
        estimate = estimate_duration(item.assignment)
        assert estimate.estimated_minutes == 90 and "fallback" in estimate.explanation.lower()


@pytest.mark.parametrize("submission, status, selected", [
    ({"workflow_state": "submitted"}, "Submitted", False),
    ({"workflow_state": "graded", "score": 0}, "Graded (review completion)", False),
    ({"workflow_state": "pending_review"}, "Pending review", False),
    ({"workflow_state": "unsubmitted"}, "Unsubmitted", True),
    ({"workflow_state": "unsubmitted", "submitted_at": "2026-11-01T00:00:00Z"}, "Submitted", False),
    ({"workflow_state": "graded", "excused": True}, "Excused", False),
    ({"workflow_state": "graded", "redo_request": True}, "Needs resubmission", True),
    (None, "Unknown", False), ({}, "Unknown", False),
])
def test_student_status_and_default_selection(record: dict, submission: object, status: str, selected: bool) -> None:
    item = convert_assignment({**record, "submission": submission}, COURSE, SITE)
    assert item.status == status and item.selected_by_default == selected


def test_other_students_submissions_do_not_indicate_personal_completion(record: dict) -> None:
    record.pop("submission")
    record["has_submitted_submissions"] = True
    item = convert_assignment(record, COURSE, SITE)
    assert item.status == "Unknown" and not item.selected_by_default


def test_missing_deadline_and_null_description_are_supported(record: dict) -> None:
    item = convert_assignment({**record, "due_at": None, "description": None}, COURSE, SITE)
    assert item.assignment.due_at is None and item.assignment.description == ""


@pytest.mark.parametrize("changes", [
    {"id": True}, {"id": None}, {"course_id": 99}, {"name": ""},
    {"due_at": "2026-11-01T12:00:00"}, {"due_at": "PRIVATE-invalid-date"},
    {"points_possible": float("nan")}, {"points_possible": float("inf")},
])
def test_invalid_records_report_no_private_values(record: dict, changes: dict) -> None:
    with pytest.raises(ValueError) as error:
        convert_assignment({**record, **changes}, COURSE, SITE)
    assert "PRIVATE" not in str(error.value)


def test_import_reports_course_failure_and_invalid_records_without_hiding_good_work(record: dict) -> None:
    client = Mock()
    client.list_assignments.side_effect = [
        [record, {**record, "id": 8, "due_at": "PRIVATE"}],
        CanvasClientError("HTTP 403: access denied"),
    ]
    result = import_courses(client, [COURSE, {"id": 43, "name": "Other course"}], SITE)
    assert len(result.items) == 1
    assert len(result.warnings) == 2
    assert "course 42" in result.warnings[0] and "record 2" in result.warnings[0]
    assert "course 43" in result.warnings[1] and "403" in result.warnings[1]
    assert "PRIVATE" not in str(result.warnings)
    assert client.list_assignments.call_count == 2


def test_duplicate_assignment_is_reported_and_not_double_scheduled(record: dict) -> None:
    client = Mock()
    client.list_assignments.return_value = [record, record]
    result = import_courses(client, [COURSE], SITE)
    assert len(result.items) == 1 and "duplicate" in result.warnings[0]
