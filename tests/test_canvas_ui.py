"""Real Streamlit interactions with Canvas methods replaced by mocks."""

from datetime import date
from pathlib import Path
from unittest.mock import Mock

import pytest
from streamlit.testing.v1 import AppTest
from streamlit.proto.TextInput_pb2 import TextInput

from workload_planner.canvas_client import CanvasClient, CanvasClientError

APP = Path(__file__).resolve().parents[1] / "streamlit_app.py"
SITE = "https://canvas.example.edu"
FIRST_ID = "canvas:canvas.example.edu:42:7"
SECOND_ID = "canvas:canvas.example.edu:42:8"


@pytest.fixture
def canvas(monkeypatch: pytest.MonkeyPatch) -> tuple[Mock, Mock]:
    courses = Mock(return_value=[{"id": 42, "name": "Python course"}, {"id": 43}])
    assignments = Mock(return_value=[
        {"id": 7, "course_id": 42, "name": "Upload task", "due_at": "2026-11-12T22:00:00Z",
         "submission_types": ["online_upload"], "submission": {"workflow_state": "unsubmitted"}},
        {"id": 8, "course_id": 42, "name": "Completed quiz", "due_at": None,
         "submission_types": ["online_quiz"], "submission": {"workflow_state": "graded"}},
    ])
    monkeypatch.setattr(CanvasClient, "list_courses", courses)
    monkeypatch.setattr(CanvasClient, "list_assignments", assignments)
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


def test_import_shows_all_statuses_and_selects_only_unsubmitted_work(canvas: tuple[Mock, Mock]) -> None:
    app = imported(canvas_page())
    assert not app.exception and not app.error
    canvas[1].assert_called_once_with(42)
    table = app.dataframe[0].value
    assert table["Status"].tolist() == ["Unsubmitted", "Graded (review completion)"]
    assert table["Type"].tolist() == ["unknown", "quiz"]
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


def test_invalid_configuration_does_not_fetch_courses(canvas: tuple[Mock, Mock]) -> None:
    app = canvas_page()
    app.text_input(key="canvas_base_url").set_value("http://canvas.example.edu")
    app.text_input(key="canvas_token").set_value("synthetic-token")
    app.button(key="canvas_connect").click().run()
    assert not app.exception and app.error
    canvas[0].assert_not_called()
