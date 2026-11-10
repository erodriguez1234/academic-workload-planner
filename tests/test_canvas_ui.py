"""Real Streamlit interactions with Canvas methods replaced by mocks."""

from datetime import date, datetime, time
from pathlib import Path
from unittest.mock import Mock
from zoneinfo import ZoneInfo

import pytest
from streamlit.testing.v1 import AppTest
from streamlit.proto.TextInput_pb2 import TextInput

from workload_planner.canvas_client import CanvasClient, CanvasClientError
from workload_planner.scheduling_models import AvailabilityPeriod, SchedulingPreferences
from tests.test_scheduler import assert_schedule_constraints

APP = Path(__file__).resolve().parents[1] / "streamlit_app.py"
SITE = "https://canvas.example.edu"
FIRST_ID = "canvas:canvas.example.edu:42:7"
SECOND_ID = "canvas:canvas.example.edu:42:8"


@pytest.fixture
def canvas(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> tuple[Mock, Mock]:
    monkeypatch.setattr("workload_planner.duration_storage.DEFAULT_PATH", tmp_path / "minutes.json")
    monkeypatch.setattr("workload_planner.planning_defaults.current_planning_dates", lambda zone_name: (date(2026, 11, 7), time(9), date(2026, 11, 20)))
    courses = Mock(return_value=[{"id": 42, "name": "Python course"}, {"id": 43}])
    assignments = Mock(return_value=[
        {"id": 7, "course_id": 42, "name": "Upload task", "due_at": "2026-11-12T22:00:00Z",
         "submission_types": ["online_upload"], "submission": {"workflow_state": "unsubmitted"}},
        {"id": 8, "course_id": 42, "name": "Completed quiz", "due_at": None,
         "submission_types": ["online_quiz"], "submission": {"workflow_state": "graded"}},
    ])
    monkeypatch.setattr(CanvasClient, "list_courses", courses)
    monkeypatch.setattr(CanvasClient, "list_assignments", assignments)
    monkeypatch.setattr("workload_planner.canvas_ui.load_token", Mock(return_value=None))
    monkeypatch.setattr("workload_planner.canvas_ui.save_token", Mock())
    monkeypatch.setattr("workload_planner.canvas_ui.forget_token", Mock())
    # Fail closed if a UI change accidentally uses another transport path.
    monkeypatch.setattr("workload_planner.canvas_client.build_opener", Mock(side_effect=lambda *args: Mock(open=Mock(side_effect=AssertionError("unexpected network")))))
    return courses, assignments


def canvas_page() -> AppTest:
    app = AppTest.from_file(str(APP), default_timeout=15).run()
    app.radio(key="data_source").set_value("Canvas").run()
    return app


def connect(app: AppTest) -> AppTest:
    app.text_input(key="canvas_base_url").set_value(SITE)
    app.text_input(key="canvas_token").set_value("synthetic-token")
    return app.button(key="canvas_connect").click().run()


def imported(app: AppTest) -> AppTest:
    connect(app)
    app.multiselect(key="canvas_course_ids").set_value([42]).run()
    return app.button(key="canvas_import").click().run()


def test_initial_load_and_mode_switch_do_not_contact_canvas(canvas: tuple[Mock, Mock]) -> None:
    app = canvas_page()
    assert not app.exception
    assert app.text_input(key="canvas_token").proto.type == TextInput.PASSWORD
    for method in canvas:
        method.assert_not_called()


def test_connection_lists_courses_only_and_explains_restricted_course(canvas: tuple[Mock, Mock]) -> None:
    app = connect(canvas_page())
    assert not app.exception and not app.error
    canvas[0].assert_called_once()
    canvas[1].assert_not_called()
    assert app.multiselect(key="canvas_course_ids").options == ["Python course (42)", "Course 43 (name unavailable)"]
    assert any("name unavailable" in warning.value for warning in app.warning)


def test_successful_connection_hides_token_form_and_keeps_disconnect(canvas: tuple[Mock, Mock]) -> None:
    app = connect(canvas_page())
    assert not app.exception
    assert any(message.value == "Connected to Canvas." for message in app.success)
    assert not any(widget.key == "canvas_token" for widget in app.text_input)
    assert not any(button.key == "canvas_connect" for button in app.button)
    assert app.button(key="canvas_disconnect")
    app.run()
    assert not any(widget.key == "canvas_token" for widget in app.text_input)
    canvas[0].assert_called_once()


def test_disconnect_restores_empty_token_form_and_allows_reconnection(canvas: tuple[Mock, Mock]) -> None:
    app = connect(canvas_page())
    app.button(key="canvas_disconnect").click().run()
    assert not app.exception
    assert app.text_input(key="canvas_token").value == ""
    assert app.button(key="canvas_connect")
    connect(app)
    assert not app.exception and not app.error
    assert not any(widget.key == "canvas_token" for widget in app.text_input)
    assert canvas[0].call_count == 2


def test_import_shows_all_statuses_and_selects_only_unsubmitted_work(canvas: tuple[Mock, Mock]) -> None:
    app = imported(canvas_page())
    assert not app.exception and not app.error
    canvas[1].assert_called_once_with(42)
    table = app.dataframe[0].value
    assert table["Status"].tolist() == ["Unsubmitted", "Graded (review completion)"]
    assert table["Type"].tolist() == ["unknown", "quiz"]
    assert table["Deadline"].tolist() == ["November 12, 2026 2:00PM PST", "No deadline"]
    assert app.multiselect(key="canvas_assignment_ids").value == [FIRST_ID]
    assert app.number_input(key=f"minutes_{FIRST_ID}").value == 90
    app.run()
    canvas[1].assert_called_once()


def test_selection_reaches_scheduler_and_changes_hide_old_results(canvas: tuple[Mock, Mock]) -> None:
    app = imported(canvas_page())
    app.date_input(key="start_date").set_value(date(2026, 11, 4)).run()
    app.date_input(key="end_date").set_value(date(2026, 11, 14)).run()
    app.button(key="generate").click().run()
    assert not app.exception
    assert [task.assignment_id for task in app.session_state["result"].tasks] == [FIRST_ID]
    app.multiselect(key="canvas_assignment_ids").set_value([SECOND_ID]).run()
    assert any("Inputs changed" in message.value for message in app.info)
    app.button(key="generate").click().run()
    assert [task.assignment_id for task in app.session_state["result"].tasks] == [SECOND_ID]


def test_empty_selection_does_not_schedule_everything(canvas: tuple[Mock, Mock]) -> None:
    app = imported(canvas_page())
    app.multiselect(key="canvas_assignment_ids").set_value([]).run()
    assert not app.exception
    assert not any(button.key == "generate" for button in app.button)


def test_failed_refresh_clears_old_import_and_reports_gap(canvas: tuple[Mock, Mock]) -> None:
    app = imported(canvas_page())
    canvas[1].side_effect = CanvasClientError("HTTP 403: access denied")
    app.button(key="canvas_import").click().run()
    assert not app.exception
    assert any("403" in warning.value for warning in app.warning)
    assert len(app.dataframe) == 0


def test_changing_courses_requires_explicit_reimport(canvas: tuple[Mock, Mock]) -> None:
    app = imported(canvas_page())
    app.multiselect(key="canvas_course_ids").set_value([43]).run()
    assert not app.exception and len(app.dataframe) == 0
    canvas[1].assert_called_once()


def test_changing_site_hides_previous_private_data(canvas: tuple[Mock, Mock]) -> None:
    app = imported(canvas_page())
    app.text_input(key="canvas_base_url").set_value("https://other.example.edu").run()
    assert not app.exception and len(app.dataframe) == 0
    canvas[1].assert_called_once()


def test_disconnect_removes_connection_and_imported_data(canvas: tuple[Mock, Mock]) -> None:
    app = imported(canvas_page())
    app.button(key="canvas_disconnect").click().run()
    assert not app.exception and len(app.dataframe) == 0
    assert "canvas_client" not in app.session_state
    assert "canvas_snapshot" not in app.session_state


def test_sample_mode_still_generates_original_demo(canvas: tuple[Mock, Mock]) -> None:
    app = imported(canvas_page())
    app.radio(key="data_source").set_value("Sample data").run()
    app.button(key="generate").click().run()
    assert not app.exception
    assert sum(session.duration_minutes for session in app.session_state["result"].sessions) == 390
    assert sum(work.remaining_minutes for work in app.session_state["result"].unscheduled_work) == 60


def test_connection_failure_is_readable_and_does_not_expose_token(canvas: tuple[Mock, Mock]) -> None:
    canvas[0].side_effect = CanvasClientError("HTTP 401: check token expiration")
    app = connect(canvas_page())
    assert not app.exception
    assert any("401" in error.value for error in app.error)
    assert "synthetic-token" not in " ".join(error.value for error in app.error)
    assert app.text_input(key="canvas_token")
    assert app.button(key="canvas_connect")


def test_invalid_configuration_does_not_fetch_courses(canvas: tuple[Mock, Mock]) -> None:
    app = canvas_page()
    app.text_input(key="canvas_base_url").set_value("http://canvas.example.edu")
    app.text_input(key="canvas_token").set_value("synthetic-token")
    app.button(key="canvas_connect").click().run()
    assert not app.exception and app.error
    canvas[0].assert_not_called()


def test_remembered_token_works_in_a_fresh_session_without_prefilling_field(canvas: tuple[Mock, Mock], monkeypatch: pytest.MonkeyPatch) -> None:
    saved = {}
    monkeypatch.setattr("workload_planner.canvas_ui.save_token", lambda site, token: saved.update({site: token}))
    monkeypatch.setattr("workload_planner.canvas_ui.load_token", lambda site: saved.get(site))
    app = canvas_page()
    app.checkbox(key="canvas_remember_token").check()
    connect(app)
    assert saved == {SITE: "synthetic-token"}
    refreshed = canvas_page()
    assert not refreshed.exception and not refreshed.error
    assert not any(widget.key == "canvas_token" for widget in refreshed.text_input)
    assert canvas[0].call_count == 2
    refreshed.run()
    assert canvas[0].call_count == 2  # Ordinary reruns do not repeat the resume read.


def test_successful_connection_does_not_save_without_opt_in(canvas: tuple[Mock, Mock], monkeypatch: pytest.MonkeyPatch) -> None:
    save = Mock()
    monkeypatch.setattr("workload_planner.canvas_ui.save_token", save)
    connect(canvas_page())
    save.assert_not_called()


def test_invalid_token_is_not_saved(canvas: tuple[Mock, Mock], monkeypatch: pytest.MonkeyPatch) -> None:
    save = Mock()
    monkeypatch.setattr("workload_planner.canvas_ui.save_token", save)
    canvas[0].side_effect = CanvasClientError("HTTP 401: token expired")
    app = canvas_page()
    app.checkbox(key="canvas_remember_token").check()
    connect(app)
    save.assert_not_called()


def test_forget_saved_token_disconnects_and_clears_import(canvas: tuple[Mock, Mock], monkeypatch: pytest.MonkeyPatch) -> None:
    forget = Mock()
    monkeypatch.setattr("workload_planner.canvas_ui.forget_token", forget)
    app = imported(canvas_page())
    app.button(key="canvas_forget_token").click().run()
    forget.assert_called_once_with(SITE)
    assert not app.exception
    assert "canvas_client" not in app.session_state and len(app.dataframe) == 0


def test_storage_failure_keeps_successful_session_connection(canvas: tuple[Mock, Mock], monkeypatch: pytest.MonkeyPatch) -> None:
    from workload_planner.credentials import CredentialStoreError
    monkeypatch.setattr("workload_planner.canvas_ui.save_token", Mock(side_effect=CredentialStoreError("Keychain unavailable")))
    app = canvas_page()
    app.checkbox(key="canvas_remember_token").check()
    connect(app)
    assert not app.exception and "canvas_client" in app.session_state
    assert any("Keychain" in warning.value for warning in app.warning)


def test_screenshot_deadline_uses_local_date_and_ampm(canvas: tuple[Mock, Mock]) -> None:
    canvas[1].return_value = [{
        "id": 7, "course_id": 42, "name": "Synthetic homework",
        "due_at": "2026-11-07T07:59:00Z", "submission_types": ["online_upload"],
        "submission": {"workflow_state": "unsubmitted"},
    }]
    app = imported(canvas_page())
    assert app.dataframe[0].value["Deadline"].tolist() == ["November 6, 2026 11:59PM PST"]
    assert app.dataframe[1].value["Deadline"].tolist() == ["November 6, 2026 11:59PM PST"]


def test_saved_expired_token_shows_auth_error_and_keeps_field_empty(canvas: tuple[Mock, Mock], monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("workload_planner.canvas_ui.load_token", Mock(return_value="synthetic-expired-token"))
    canvas[0].side_effect = CanvasClientError("HTTP 401: token expired")
    app = canvas_page()
    app.button(key="canvas_connect").click().run()
    assert not app.exception and any("401" in error.value for error in app.error)
    assert app.text_input(key="canvas_token").value == ""
    assert "synthetic-expired-token" not in " ".join(error.value for error in app.error)


def test_manual_token_does_not_require_keychain_access(canvas: tuple[Mock, Mock], monkeypatch: pytest.MonkeyPatch) -> None:
    load = Mock(side_effect=AssertionError("should not read Keychain"))
    monkeypatch.setattr("workload_planner.canvas_ui.load_token", load)
    app = connect(canvas_page())
    assert not app.exception and not app.error
    load.assert_not_called()


def test_no_saved_token_has_clear_feedback_without_a_canvas_request(canvas: tuple[Mock, Mock]) -> None:
    app = canvas_page()
    app.button(key="canvas_connect").click().run()
    assert not app.exception and any("No saved token" in error.value for error in app.error)
    canvas[0].assert_not_called()


@pytest.mark.parametrize("pasted", [" synthetic-token ", "synthetic-token\n", "\r\nsynthetic-token\r\n", "\tsynthetic-token\t"])
def test_pasted_token_trims_outer_whitespace_before_connecting_and_saving(canvas: tuple[Mock, Mock], monkeypatch: pytest.MonkeyPatch, pasted: str) -> None:
    save = Mock()
    monkeypatch.setattr("workload_planner.canvas_ui.save_token", save)
    app = canvas_page()
    app.text_input(key="canvas_base_url").set_value(SITE)
    app.text_input(key="canvas_token").set_value(pasted)
    app.checkbox(key="canvas_remember_token").check()
    app.button(key="canvas_connect").click().run()
    assert not app.exception and not app.error
    canvas[0].assert_called_once()
    save.assert_called_once_with(SITE, "synthetic-token")
    assert app.session_state["canvas_client"]._token == "synthetic-token"


def test_internal_whitespace_is_reported_without_sending_a_modified_token(canvas: tuple[Mock, Mock]) -> None:
    app = canvas_page()
    app.text_input(key="canvas_token").set_value("synthetic token")
    app.button(key="canvas_connect").click().run()
    assert not app.exception
    assert any("inside" in error.value for error in app.error)
    canvas[0].assert_not_called()


def test_canvas_has_current_dates_while_sample_keeps_its_demo(canvas: tuple[Mock, Mock]) -> None:
    app = imported(canvas_page())
    assert app.date_input(key="start_date").value == date(2026, 11, 7)
    assert app.date_input(key="end_date").value == date(2026, 11, 20)
    app.date_input(key="end_date").set_value(date(2026, 11, 15)).run()
    app.radio(key="data_source").set_value("Sample data").run()
    assert app.date_input(key="start_date").value == date(2026, 10, 10)
    app.radio(key="data_source").set_value("Canvas").run()
    assert app.date_input(key="end_date").value == date(2026, 11, 15)


def test_adjustment_survives_deselection_reimport_and_fresh_browser_session(canvas: tuple[Mock, Mock]) -> None:
    app = imported(canvas_page())
    app.number_input(key=f"minutes_{FIRST_ID}").set_value(75).run()
    app.multiselect(key="canvas_assignment_ids").set_value([]).run()
    app.multiselect(key="canvas_assignment_ids").set_value([FIRST_ID]).run()
    assert app.number_input(key=f"minutes_{FIRST_ID}").value == 75
    app.button(key="canvas_import").click().run()
    assert app.number_input(key=f"minutes_{FIRST_ID}").value == 75
    refreshed = imported(canvas_page())
    assert refreshed.number_input(key=f"minutes_{FIRST_ID}").value == 75
    assert refreshed.dataframe[1].value["Original estimate (min)"].tolist() == [90]


def test_canvas_schedule_accounts_for_adjusted_work_and_all_failure_reasons(canvas: tuple[Mock, Mock]) -> None:
    def task(number: int, due_at: str | None) -> dict:
        return {"id": number, "course_id": 42, "name": f"Synthetic task {number}",
                "due_at": due_at, "submission_types": ["online_upload"],
                "submission": {"workflow_state": "unsubmitted"}}
    canvas[1].return_value = [task(7, "2026-11-08T04:00:00Z"), task(8, None), task(9, "2026-11-06T00:00:00Z")]
    app = imported(canvas_page())
    app.number_input(key=f"minutes_{FIRST_ID}").set_value(150).run()
    app.number_input(key="daily_limit").set_value(60).run()
    app.button(key="generate").click().run()
    assert not app.exception and not app.error
    result = app.session_state["result"]
    assert sum(task.required_minutes for task in result.tasks) == 330
    assert sum(session.duration_minutes for session in result.sessions) == 60
    assert sum(work.remaining_minutes for work in result.unscheduled_work) == 270
    assert {work.reason for work in result.unscheduled_work} == {"missing_deadline", "deadline_not_after_start", "unplaced_by_greedy"}
    for task in result.tasks:
        placed = sum(s.duration_minutes for s in result.sessions if s.assignment_id == task.assignment_id)
        remaining = sum(w.remaining_minutes for w in result.unscheduled_work if w.assignment_id == task.assignment_id)
        assert placed + remaining == task.required_minutes
    assert sum("Could not schedule" in warning.value for warning in app.warning) == 3
    assert [metric.value for metric in app.metric] == ["330", "60", "270"]
    zone = ZoneInfo("America/Los_Angeles")
    assert_schedule_constraints(
        result,
        [AvailabilityPeriod(datetime(2026, 11, 7, 18, tzinfo=zone), datetime(2026, 11, 7, 20, tzinfo=zone))],
        SchedulingPreferences(datetime(2026, 11, 7, 9, tzinfo=zone), zone, 60, 60),
    )


def test_duration_save_failure_keeps_in_memory_override_and_warns(canvas: tuple[Mock, Mock], monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("workload_planner.duration_storage.save_adjustment", Mock(side_effect=OSError("private details")))
    app = imported(canvas_page())
    app.number_input(key=f"minutes_{FIRST_ID}").set_value(75).run()
    assert not app.exception and app.number_input(key=f"minutes_{FIRST_ID}").value == 75
    assert any("could not be saved" in warning.value for warning in app.warning)


def test_current_dates_action_keeps_minutes_and_invalid_timezone_is_recoverable(canvas: tuple[Mock, Mock]) -> None:
    app = imported(canvas_page())
    app.number_input(key=f"minutes_{FIRST_ID}").set_value(75).run()
    app.date_input(key="start_date").set_value(date(2026, 11, 8)).run()
    app.button(key="use_current_dates").click().run()
    assert app.date_input(key="start_date").value == date(2026, 11, 7)
    assert app.number_input(key=f"minutes_{FIRST_ID}").value == 75


def test_switching_to_canvas_with_invalid_timezone_still_allows_correction(canvas: tuple[Mock, Mock], monkeypatch: pytest.MonkeyPatch) -> None:
    from zoneinfo import ZoneInfoNotFoundError
    def defaults(zone_name: str) -> tuple:
        if zone_name != "America/Los_Angeles":
            raise ZoneInfoNotFoundError("invalid")
        return date(2026, 11, 7), time(9), date(2026, 11, 20)
    monkeypatch.setattr("workload_planner.planning_defaults.current_planning_dates", defaults)
    app = AppTest.from_file(str(APP), default_timeout=15).run()
    app.text_input(key="student_timezone").set_value("Not/AZone").run()
    app.radio(key="data_source").set_value("Canvas").run()
    assert not app.exception and app.error
    app.text_input(key="student_timezone").set_value("America/Los_Angeles").run()
    app.button(key="use_current_dates").click().run()
    assert not app.exception and not app.error
