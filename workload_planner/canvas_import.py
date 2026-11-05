"""Convert Canvas records without changing estimator or scheduler models."""

from dataclasses import dataclass
from datetime import datetime
from math import isfinite
from urllib.parse import urlsplit

from workload_planner.canvas_client import CanvasClient, CanvasClientError
from workload_planner.models import Assignment


@dataclass(frozen=True)
class ImportedAssignment:
    """Keep student submission metadata beside the existing Assignment."""

    assignment: Assignment
    status: str
    selected_by_default: bool


@dataclass(frozen=True)
class CanvasImportResult:
    """Successful records plus explicit access or conversion gaps."""

    items: tuple[ImportedAssignment, ...]
    warnings: tuple[str, ...]


def _positive_id(value: object) -> bool:
    return type(value) is int and value > 0


def _submission_status(record: dict[str, object]) -> tuple[str, bool]:
    submission = record.get("submission")
    if not isinstance(submission, dict):
        return "Unknown", False
    if submission.get("excused") is True:
        return "Excused", False
    if submission.get("redo_request") is True:
        return "Needs resubmission", True
    state = submission.get("workflow_state")
    if state == "graded":
        return "Graded (review completion)", False
    if state == "pending_review":
        return "Pending review", False
    if state == "submitted" or submission.get("submitted_at"):
        return "Submitted", False
    if state == "unsubmitted":
        return "Unsubmitted", True
    return "Unknown", False


def convert_assignment(
    record: dict[str, object], course: dict[str, object], site_url: str,
) -> ImportedAssignment:
    """Preserve the user's effective due_at; never infer type from prose.

    The API applies date overrides for the requesting student. all_dates can
    contain other students' deadlines and must not replace due_at. Missing
    due_at is invalid; explicit null is a legitimate assignment with no deadline.
    Errors identify fields rather than echoing private response values.
    """
    course_id = course.get("id")
    assignment_id = record.get("id")
    if not _positive_id(course_id) or not _positive_id(assignment_id):
        raise ValueError("course and assignment IDs must be positive integers")
    if record.get("course_id") != course_id:
        raise ValueError("course_id does not match the selected course")
    if "due_at" not in record:
        raise ValueError("missing due_at field")
    deadline = record["due_at"]
    if deadline is not None:
        try:
            deadline = datetime.fromisoformat(deadline)
        except (TypeError, ValueError):
            raise ValueError("due_at must be a valid timezone-aware ISO datetime or null") from None
    types = record.get("submission_types")
    kind = "unknown"
    if types == ["online_quiz"]:
        kind = "quiz"
    elif types == ["discussion_topic"]:
        kind = "discussion"
    points = record.get("points_possible")
    if isinstance(points, (float, int)) and not isfinite(points):
        raise ValueError("points_possible must be finite")
    description = record.get("description")
    if description is None:
        description = ""
    try:
        assignment = Assignment(
            assignment_id=f"canvas:{urlsplit(site_url).netloc.lower()}:{course_id}:{assignment_id}",
            course=course.get("name"), title=record.get("name"),
            assignment_type=kind, due_at=deadline, points_possible=points,
            description=description,
        )
    except (TypeError, ValueError):
        raise ValueError("invalid course name, title, deadline, points, or description") from None
    status, selected = _submission_status(record)
    return ImportedAssignment(assignment, status, selected)


def import_courses(
    client: CanvasClient, courses: list[dict[str, object]], site_url: str,
) -> CanvasImportResult:
    """Fetch selected courses independently and report every observed gap.

    A failed course contributes no partial page data. Invalid records are
    reported by course ID and position; valid work remains available for review.
    """
    items: list[ImportedAssignment] = []
    warnings: list[str] = []
    seen: set[str] = set()
    for course in courses:
        course_id = course.get("id")
        if not _positive_id(course_id):
            warnings.append("Skipped a course with an invalid or missing ID; import is incomplete.")
            continue
        try:
            records = client.list_assignments(course_id)
        except CanvasClientError as error:
            warnings.append(f"Could not import course {course_id}: {error}")
            continue
        for position, record in enumerate(records, start=1):
            try:
                item = convert_assignment(record, course, site_url)
                if item.assignment.assignment_id in seen:
                    raise ValueError("duplicate assignment ID")
            except ValueError as error:
                warnings.append(f"Skipped course {course_id}, record {position}: {error}; import is incomplete.")
                continue
            seen.add(item.assignment.assignment_id)
            items.append(item)
    return CanvasImportResult(tuple(items), tuple(warnings))
