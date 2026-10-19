"""Functions for loading assignment data into planner models."""

import json
from datetime import datetime
from pathlib import Path

from workload_planner.models import Assignment


def load_assignments(path: str | Path) -> list[Assignment]:
    """Load a UTF-8 JSON list into validated assignments in input order.

    Deadlines must be ISO 8601 strings with timezone information, or null.
    Missing points and descriptions use the Assignment model's defaults.
    Invalid JSON or records raise ValueError; file-access errors propagate.
    No partial list is returned if any record is invalid.
    """
    path = Path(path)
    with path.open(encoding="utf-8") as file:
        try:
            records = json.load(file)
        except json.JSONDecodeError as error:
            raise ValueError(
                f"Invalid JSON in {path}: {error.msg} "
                f"(line {error.lineno}, column {error.colno})"
            ) from error

    if not isinstance(records, list):
        raise ValueError(f"{path}: expected a list of assignment records")

    required_fields = ("assignment_id", "course", "title", "assignment_type", "due_at")
    assignments: list[Assignment] = []

    for record_number, record in enumerate(records, start=1):
        if not isinstance(record, dict):
            raise ValueError(f"Record {record_number}: expected a JSON object")

        for field_name in required_fields:
            if field_name not in record:
                raise ValueError(
                    f"Record {record_number}: missing required field {field_name}"
                )

        # Convert a copy so the parsed input retains its original values.
        values = record.copy()
        deadline = values["due_at"]
        if deadline is not None:
            if not isinstance(deadline, str):
                raise ValueError(
                    f"Record {record_number}: due_at must be an ISO 8601 string or null"
                )
            try:
                values["due_at"] = datetime.fromisoformat(deadline)
            except ValueError as error:
                raise ValueError(
                    f"Record {record_number}: due_at must be a valid ISO 8601 datetime"
                ) from error

        try:
            assignment = Assignment(**values)
        except (TypeError, ValueError) as error:
            raise ValueError(f"Record {record_number}: {error}") from error

        assignments.append(assignment)

    return assignments
