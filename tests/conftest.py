"""Never read or change the owner's real resume preferences during tests."""

import pytest


@pytest.fixture(autouse=True)
def isolated_resume_preferences(monkeypatch, tmp_path):
    monkeypatch.setattr("workload_planner.local_preferences.DEFAULT_PATH", tmp_path / "planner_preferences.json")
