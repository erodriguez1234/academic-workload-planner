"""Real page tests: calendars affect planning; only approved previews can write."""

from datetime import datetime, timezone
from unittest.mock import Mock

import pytest

from tests.test_canvas_ui import canvas, canvas_page, imported, FIRST_ID
from workload_planner.calendar_export import session_event_id
from workload_planner.calendar_planning import BusyPeriod
from workload_planner.google_auth import GoogleConnectionError


@pytest.fixture
def calendar_api(monkeypatch: pytest.MonkeyPatch, tmp_path) -> tuple:
    connection = Mock(calendar_id="planner", subject="user", client_id="client", marker="owner", creation_pending=False)
    api = Mock(connection=connection)
    api.check_planner_calendar.return_value = {"id": "planner", "summary": "Academic Workload Planner", "description": "Academic Workload Planner / owner"}
    api.list_planner_events.return_value = []
    api.get_event.return_value = None
    api.busy_periods.return_value = ()
    api.list_calendars.return_value = [{"id": "primary-address", "summary": "Personal", "primary": True}, {"id": "work", "summary": "Work"}]
    monkeypatch.setattr("workload_planner.google_ui.connect_google", Mock(return_value=connection))
    monkeypatch.setattr("workload_planner.google_ui.GoogleCalendarClient", Mock(return_value=api))
    monkeypatch.setattr("workload_planner.calendar_export_ui.GoogleCalendarClient", Mock(return_value=api))
    monkeypatch.setattr("workload_planner.calendar_export.DEFAULT_LEDGER_PATH", tmp_path / "exports.json")
    monkeypatch.setattr("workload_planner.calendar_export.utc_now", lambda: datetime(2026, 11, 7, 16, tzinfo=timezone.utc))
    return api, connection


def connected_app():
    app = imported(canvas_page())
    return app.button(key="google_connect").click().run()


def test_generate_places_sessions_around_existing_calendar_event(canvas, calendar_api) -> None:
    api, _ = calendar_api
    # November 7 6–7PM Pacific = November 8 02–03 UTC.
    api.busy_periods.return_value = (BusyPeriod(datetime(2026, 11, 8, 2, tzinfo=timezone.utc), datetime(2026, 11, 8, 3, tzinfo=timezone.utc)),)
    app = connected_app()
    api.busy_periods.assert_not_called()
    app.button(key="generate").click().run()
    assert not app.exception and not app.error
    result = app.session_state["result"]
    assert result.sessions[0].start_at.hour == 19
    assert sum(s.duration_minutes for s in result.sessions) == 90
    api.insert_event.assert_not_called()


def test_failed_calendar_read_blocks_generation_instead_of_assuming_free(canvas, calendar_api) -> None:
    api, _ = calendar_api
    api.busy_periods.side_effect = GoogleConnectionError("Calendar busy-time access denied")
    app = connected_app()
    app.button(key="generate").click().run()
    assert not app.exception and app.error
    assert app.session_state["result"] is None


def test_calendar_selection_changes_invalidate_a_generated_plan(canvas, calendar_api) -> None:
    api, _ = calendar_api
    app = connected_app()
    app.button(key="generate").click().run()
    app.button(key="load_conflict_calendars").click().run()
    app.multiselect(key="google_extra_calendars").set_value(["work"]).run()
    assert any("Inputs changed" in message.value for message in app.info)
    assert not any(button.key == "export_preview" for button in app.button)


def test_preview_and_approval_are_required_before_export(canvas, calendar_api) -> None:
    api, connection = calendar_api
    app = connected_app()
    app.button(key="generate").click().run()
    options = app.multiselect(key="export_sessions").options
    first = app.session_state["result"].sessions[0]
    event_id = session_event_id(connection, first)
    app.multiselect(key="export_sessions").set_value([event_id]).run()
    app.button(key="export_preview").click().run()
    api.insert_event.assert_not_called()
    assert app.button(key="export_send").disabled
    app.checkbox(key="export_approve").check().run()
    assert not app.button(key="export_send").disabled
    api.insert_event.side_effect = lambda body: {**body, "status": "confirmed"}
    app.button(key="export_send").click().run()
    assert not app.exception
    api.insert_event.assert_called_once()


def test_preview_conflict_disables_writes_and_explains_regeneration(canvas, calendar_api) -> None:
    api, connection = calendar_api
    app = connected_app()
    app.button(key="generate").click().run()
    first = app.session_state["result"].sessions[0]
    app.multiselect(key="export_sessions").set_value([session_event_id(connection, first)]).run()
    api.busy_periods.return_value = (BusyPeriod(first.start_at, first.end_at),)
    app.button(key="export_preview").click().run()
    assert not app.exception and app.button(key="export_send").disabled
    assert any("conflict" in warning.value.lower() for warning in app.warning)
    api.insert_event.assert_not_called()


def test_regeneration_credits_exported_minutes_without_scheduling_them_twice(canvas, calendar_api) -> None:
    api, connection = calendar_api
    app = connected_app()
    app.button(key="generate").click().run()
    first = app.session_state["result"].sessions[0]
    key = session_event_id(connection, first)
    app.multiselect(key="export_sessions").set_value([key]).run()
    app.button(key="export_preview").click().run()
    app.checkbox(key="export_approve").check().run()
    events = {}
    def insert(body):
        events[body["id"]] = {**body, "status": "confirmed"}
        return events[body["id"]]
    api.insert_event.side_effect = insert
    app.button(key="export_send").click().run()
    api.list_planner_events.return_value = list(events.values())
    api.get_event.side_effect = events.get
    api.busy_periods.return_value = (BusyPeriod(first.start_at, first.end_at),)
    app.button(key="generate").click().run()
    assert not app.exception and not app.error
    result = app.session_state["result"]
    assert sum(s.duration_minutes for s in result.sessions) == 90
    assert result.sessions.count(first) == 1
    assert key not in app.multiselect(key="export_sessions").options
    api.insert_event.assert_called_once()


def test_changed_session_selection_requires_fresh_preview_and_approval(canvas, calendar_api) -> None:
    api, connection = calendar_api
    app = connected_app()
    app.button(key="generate").click().run()
    key = session_event_id(connection, app.session_state["result"].sessions[0])
    app.multiselect(key="export_sessions").set_value([key]).run()
    app.button(key="export_preview").click().run()
    app.checkbox(key="export_approve").check().run()
    app.multiselect(key="export_sessions").set_value([]).run()
    assert not app.exception
    assert not any(b.key == "export_send" for b in app.button)
    api.insert_event.assert_not_called()
