"""Google controls use explicit actions; no browser or live API in AppTest."""

from pathlib import Path
from unittest.mock import Mock

import pytest
from streamlit.testing.v1 import AppTest

from workload_planner.google_auth import GoogleConnectionError

APP = Path(__file__).resolve().parents[1] / "streamlit_app.py"


@pytest.fixture
def google(monkeypatch: pytest.MonkeyPatch) -> tuple:
    connection = Mock(calendar_id=None, creation_pending=False)
    connect = Mock(return_value=connection)
    api = Mock()
    api.create_planner_calendar.return_value = {"id": "planner-id", "summary": "Academic Workload Planner"}
    monkeypatch.setattr("workload_planner.google_ui.connect_google", connect)
    monkeypatch.setattr("workload_planner.google_ui.GoogleCalendarClient", Mock(return_value=api))
    forget = Mock()
    monkeypatch.setattr("workload_planner.google_ui.forget_google", forget)
    return connect, connection, api, forget


def page() -> AppTest:
    return AppTest.from_file(str(APP), default_timeout=15).run()


def test_page_load_does_not_open_oauth_or_create_calendar(google: tuple) -> None:
    app = page()
    assert not app.exception
    google[0].assert_not_called()
    google[2].create_planner_calendar.assert_not_called()


def test_connect_then_explicit_calendar_creation(google: tuple) -> None:
    app = page()
    app.button(key="google_connect").click().run()
    assert not app.exception
    google[0].assert_called_once_with(reauthorize=False)
    google[2].create_planner_calendar.assert_not_called()
    app.button(key="google_create_calendar").click().run()
    google[2].create_planner_calendar.assert_called_once_with("America/Los_Angeles")
    assert any("Academic Workload Planner" in caption.value for caption in app.caption)


def test_saved_calendar_is_checked_on_reconnect(google: tuple) -> None:
    google[1].calendar_id = "planner-id"
    google[2].check_planner_calendar.return_value = {"id": "planner-id", "summary": "Academic Workload Planner"}
    app = page()
    app.button(key="google_connect").click().run()
    google[2].check_planner_calendar.assert_called_once()
    google[2].create_planner_calendar.assert_not_called()


def test_auth_error_allows_explicit_reauthorization(google: tuple) -> None:
    google[0].side_effect = GoogleConnectionError("Authorization expired")
    app = page()
    app.button(key="google_connect").click().run()
    assert not app.exception and any("expired" in error.value for error in app.error)
    google[0].side_effect = None
    app.button(key="google_reauthorize").click().run()
    assert not app.exception
    assert google[0].call_args.kwargs == {"reauthorize": True}


def test_disconnect_keeps_other_planner_state_and_forget_does_not_delete_calendar(google: tuple) -> None:
    app = page()
    app.button(key="google_connect").click().run()
    app.button(key="google_disconnect").click().run()
    assert "google_connection" not in app.session_state
    assert app.date_input(key="start_date").value is not None
    google[3].assert_not_called()
    app.button(key="google_forget").click().run()
    google[3].assert_called_once()
    google[2].delete.assert_not_called()
