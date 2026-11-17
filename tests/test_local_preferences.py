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


@pytest.mark.parametrize("old_mode", ["module", "week"])
def test_old_week_settings_become_skip_without_losing_other_preferences(tmp_path, old_mode):
    path = tmp_path / "settings.json"
    manual = {"mode":"manual", "day":"2026-11-12", "clock":"23:59", "module":""}
    old = {"mode":old_mode, "day":"2026-11-09", "clock":"23:59", "module":"canvas:school.edu:42:module:3"}
    path.write_text(json.dumps({"source":"Canvas", "google_resume":True, "courses":{"https://school.edu":[42]},
        "deadline_choices":{"canvas:school.edu:42:7":manual, "canvas:school.edu:42:8":old},
        "module_weeks":{"canvas:school.edu:42:module:3":"2026-11-09"}}))
    original = path.read_text()
    loaded = load_preferences(path)
    assert loaded["deadline_choices"]["canvas:school.edu:42:7"] == {k:v for k,v in manual.items() if k != "module"}
    assert loaded["deadline_choices"]["canvas:school.edu:42:8"]["mode"] == "skip"
    assert loaded["source"] == "Canvas" and loaded["google_resume"]
    assert loaded["courses"] == {"https://school.edu":[42]}
    assert "module_weeks" not in loaded and path.read_text() == original
    save_preferences({"canvas_resume":True}, path)
    assert "module_weeks" not in json.loads(path.read_text())
