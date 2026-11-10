"""Non-secret choices for the single-user local app; credentials stay in Keychain."""

import json
import os
from pathlib import Path
from tempfile import NamedTemporaryFile
from threading import RLock
from urllib.parse import urlsplit
from datetime import date, time

DEFAULT_PATH = Path(__file__).resolve().parents[1] / ".local" / "planner_preferences.json"
_LOCK = RLock()
DEFAULTS = {"source": "Sample data", "canvas_site": "https://cilearn.csuci.edu",
            "canvas_resume": False, "google_resume": False, "courses": {}, "deadline_choices": {}, "module_weeks": {}}


def _site(value: object) -> bool:
    if not isinstance(value, str):
        return False
    try:
        url = urlsplit(value)
        return (url.scheme == "https" and bool(url.hostname) and not url.username and not url.password
                and url.path in ("", "/") and not url.query and not url.fragment
                and url.port != 0 and not any(c.isspace() for c in value))
    except ValueError:
        return False


def _validate(data: object) -> dict:
    if not isinstance(data, dict) or set(data) - set(DEFAULTS):
        raise ValueError("Saved planner preferences are invalid; the file was not overwritten.")
    result = {**DEFAULTS, **data}
    if (result["source"] not in ("Sample data", "Canvas") or not _site(result["canvas_site"])
            or any(type(result[key]) is not bool for key in ("canvas_resume", "google_resume"))
            or not isinstance(result["courses"], dict)):
        raise ValueError("Saved planner preferences are invalid; the file was not overwritten.")
    for site, ids in result["courses"].items():
        if not _site(site) or not isinstance(ids, list) or any(type(cid) is not int or cid <= 0 for cid in ids) or len(set(ids)) != len(ids):
            raise ValueError("Saved class selections are invalid; the file was not overwritten.")
    if not isinstance(result["deadline_choices"], dict) or not isinstance(result["module_weeks"], dict):
        raise ValueError("Saved planning targets are invalid.")
    for key, day in result["module_weeks"].items():
        if not isinstance(key, str) or not key.startswith("canvas:") or not isinstance(day, str) or date.fromisoformat(day).weekday() != 0:
            raise ValueError("Saved module weeks are invalid.")
    for key, choice in result["deadline_choices"].items():
        if not isinstance(key, str) or not key.startswith(("canvas:", "sample-")) or not isinstance(choice, dict) or set(choice) != {"mode", "day", "clock", "module"}:
            raise ValueError("Saved planning targets are invalid.")
        if any(not isinstance(value, str) for value in choice.values()) or choice["mode"] not in ("skip", "manual", "week", "module"):
            raise ValueError("Saved planning targets are invalid.")
        date.fromisoformat(choice["day"])
        clock = time.fromisoformat(choice["clock"])
        if clock.tzinfo is not None or clock.second or clock.microsecond:
            raise ValueError("Saved planning times must be local whole minutes.")
    return result


def load_preferences(path: Path | None = None) -> dict:
    path = DEFAULT_PATH if path is None else path
    try:
        return _validate(json.loads(path.read_text(encoding="utf-8")))
    except FileNotFoundError:
        return _validate({})
    except (ValueError, UnicodeError):
        raise ValueError("Saved planner preferences are invalid; the file was not overwritten.") from None


def save_preferences(changes: dict, path: Path | None = None) -> dict:
    """Merge validated choices, then replace atomically using owner-only permissions."""
    path = DEFAULT_PATH if path is None else path
    with _LOCK:
        result = _validate({**load_preferences(path), **changes})
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        temporary = None
        try:
            with NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as file:
                temporary = Path(file.name)
                os.fchmod(file.fileno(), 0o600)
                json.dump(result, file, indent=2)
                file.flush()
                os.fsync(file.fileno())
            os.replace(temporary, path)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
        return result
