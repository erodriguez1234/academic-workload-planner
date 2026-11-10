"""Local resume preferences contain choices, never credentials or imported content."""

import json
from pathlib import Path

import pytest

from workload_planner.local_preferences import load_preferences, save_preferences


def test_missing_preferences_have_safe_defaults_and_merge_changes(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    assert load_preferences(path)["source"] == "Sample data"
    save_preferences({"source": "Canvas", "courses": {"https://canvas.example.edu": [42, 43]}}, path)
    save_preferences({"google_resume": True}, path)
    saved = load_preferences(path)
    assert saved["source"] == "Canvas" and saved["google_resume"]
    assert saved["courses"]["https://canvas.example.edu"] == [42, 43]
    assert path.stat().st_mode & 0o777 == 0o600


@pytest.mark.parametrize("data", [{"token": "secret"}, {"google_resume": "yes"}, {"courses": {"https://school.edu": [True]}}, {"canvas_site": "https://school.edu?token=secret"}, []])
def test_invalid_or_secret_fields_are_rejected_without_overwriting(tmp_path: Path, data) -> None:
    path = tmp_path / "settings.json"
    original = json.dumps(data)
    path.write_text(original)
    with pytest.raises(ValueError):
        load_preferences(path)
    with pytest.raises(ValueError):
        save_preferences({"source": "Canvas"}, path)
    assert path.read_text() == original


def test_secret_field_cannot_be_saved(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        save_preferences({"token": "never-save"}, tmp_path / "settings.json")


def test_planning_choices_and_module_weeks_round_trip_without_assignment_content(tmp_path):
    path=tmp_path/"prefs.json"
    choice={"mode":"manual","day":"2026-11-12","clock":"23:59","module":""}
    save_preferences({"deadline_choices":{"canvas:school.edu:42:7":choice},"module_weeks":{"canvas:school.edu:42:module:3":"2026-11-09"}},path)
    saved=load_preferences(path)
    assert saved["deadline_choices"]["canvas:school.edu:42:7"]==choice
    assert saved["module_weeks"]["canvas:school.edu:42:module:3"]=="2026-11-09"
