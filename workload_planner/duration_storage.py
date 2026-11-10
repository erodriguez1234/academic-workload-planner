"""Small local preference file for Canvas duration edits; no assignment content."""

import json
import os
from pathlib import Path
from tempfile import NamedTemporaryFile

DEFAULT_PATH = Path(__file__).resolve().parents[1] / ".local" / "duration_adjustments.json"


def _valid_minutes(value: object) -> bool:
    return type(value) is int and 1 <= value <= 100_000


def load_adjustments(path: Path | None = None) -> dict[str, int]:
    """Missing preferences are normal; malformed preferences are reported."""
    path = DEFAULT_PATH if path is None else path
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except (ValueError, UnicodeError):
        raise ValueError("Saved duration adjustments are invalid") from None
    if not isinstance(data, dict) or any(
        not key.startswith("canvas:") or not _valid_minutes(minutes)
        for key, minutes in data.items()
    ):
        raise ValueError("Saved duration adjustments are invalid")
    return data


def save_adjustment(assignment_id: str, minutes: int, path: Path | None = None) -> None:
    """Merge one edit and replace the file atomically with owner-only permissions.

    Re-read before merging so an edit doesn't discard other assignment settings.
    This lightweight store is for the single-user local demo, not multiuser use.
    """
    if not assignment_id.startswith("canvas:") or not _valid_minutes(minutes):
        raise ValueError("Expected a Canvas assignment ID and 1–100000 integer minutes")
    path = DEFAULT_PATH if path is None else path
    data = load_adjustments(path)
    data[assignment_id] = minutes
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporary_path = None
    try:
        with NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as file:
            temporary_path = Path(file.name)
            os.fchmod(file.fileno(), 0o600)
            json.dump(data, file, indent=2)
        os.replace(temporary_path, path)
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
