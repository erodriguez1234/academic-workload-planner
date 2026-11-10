"""Local duration preferences contain only stable IDs and positive minutes."""

import json
from pathlib import Path

import pytest

from workload_planner.duration_storage import load_adjustments, save_adjustment

ID = "canvas:canvas.example.edu:42:7"


def test_missing_file_is_empty_and_saving_retains_other_assignments(tmp_path: Path) -> None:
    path = tmp_path / "private" / "minutes.json"
    assert load_adjustments(path) == {}
    save_adjustment(ID, 75, path)
    save_adjustment(ID + "8", 120, path)
    save_adjustment(ID, 45, path)
    assert load_adjustments(path) == {ID: 45, ID + "8": 120}
    assert path.stat().st_mode & 0o777 == 0o600
    assert json.loads(path.read_text()) == {ID: 45, ID + "8": 120}


@pytest.mark.parametrize("minutes", [True, 0, -1, 1.5, "90", 100_001])
def test_invalid_minutes_are_not_written(tmp_path: Path, minutes: object) -> None:
    path = tmp_path / "minutes.json"
    with pytest.raises(ValueError):
        save_adjustment(ID, minutes, path)
    assert not path.exists()


@pytest.mark.parametrize("body", ["invalid JSON", "[]", '{"canvas:test":0}', '{"canvas:test":true}'])
def test_invalid_existing_file_is_reported_without_overwriting_it(tmp_path: Path, body: str) -> None:
    path = tmp_path / "minutes.json"
    path.write_text(body)
    with pytest.raises(ValueError):
        load_adjustments(path)
    with pytest.raises(ValueError):
        save_adjustment(ID, 75, path)
    assert path.read_text() == body
