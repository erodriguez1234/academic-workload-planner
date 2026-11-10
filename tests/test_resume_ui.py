"""New browser sessions resume saved selections with mock credentials and APIs."""

from unittest.mock import Mock

import pytest
from streamlit.testing.v1 import AppTest

from tests.test_canvas_ui import canvas, canvas_page, SITE, APP
from tests.test_google_ui import google
from workload_planner.google_auth import GoogleConnectionError
from workload_planner.local_preferences import load_preferences, save_preferences


def fresh():
    return AppTest.from_file(str(APP), default_timeout=15).run()


def remember_canvas(app):
    app.text_input(key="canvas_base_url").set_value(SITE)
    app.text_input(key="canvas_token").set_value("synthetic")
    app.checkbox(key="canvas_remember_token").check()
    app.button(key="canvas_connect").click().run()
    app.multiselect(key="canvas_course_ids").set_value([42]).run()
    app.button(key="canvas_import").click().run()
    return app


def test_fresh_page_restores_canvas_mode_classes_and_fetches_current_assignments(canvas, monkeypatch):
    monkeypatch.setattr("workload_planner.canvas_ui.load_token", Mock(return_value="synthetic"))
    remember_canvas(canvas_page())
    canvas[0].reset_mock(); canvas[1].reset_mock()
    app = fresh()
    assert not app.exception and not app.error
    assert app.radio(key="data_source").value == "Canvas"
    assert app.multiselect(key="canvas_course_ids").value == [42]
    assert app.multiselect(key="canvas_course_ids").label == "Select Classes to Import"
    assert app.dataframe[0].value.iloc[0]["Assignment"] == "Upload task"
    assert not any(w.key == "canvas_token" for w in app.text_input)
    canvas[0].assert_called_once(); canvas[1].assert_called_once_with(42)
    app.run()
    canvas[0].assert_called_once(); canvas[1].assert_called_once_with(42)


def test_disconnect_stops_auto_resume_but_keeps_class_choices(canvas, monkeypatch):
    monkeypatch.setattr("workload_planner.canvas_ui.load_token", Mock(return_value="synthetic"))
    app = remember_canvas(canvas_page())
    app.button(key="canvas_disconnect").click().run()
    canvas[0].reset_mock(); canvas[1].reset_mock()
    app = fresh()
    assert app.text_input(key="canvas_token").value == ""
    canvas[0].assert_not_called(); canvas[1].assert_not_called()
    assert load_preferences()["courses"][SITE] == [42]


def test_unavailable_saved_class_is_reported_and_never_imported(canvas, monkeypatch):
    save_preferences({"source": "Canvas", "canvas_site": SITE, "canvas_resume": True, "courses": {SITE: [42, 99]}})
    monkeypatch.setattr("workload_planner.canvas_ui.load_token", Mock(return_value="synthetic"))
    app = fresh()
    assert not app.exception
    assert app.multiselect(key="canvas_course_ids").value == [42]
    assert any("no longer accessible" in w.value for w in app.warning)
    canvas[1].assert_called_once_with(42)
    assert load_preferences()["courses"][SITE] == [42, 99]


def test_missing_saved_token_leaves_empty_form_and_does_not_retry_on_reruns(canvas):
    save_preferences({"source": "Canvas", "canvas_site": SITE, "canvas_resume": True})
    app = fresh()
    assert not app.exception and app.text_input(key="canvas_token").value == ""
    assert any("saved token" in e.value.lower() for e in app.error)
    app.run()
    canvas[0].assert_not_called()


def test_saved_google_resumes_noninteractively_once_without_calendar_creation(google):
    save_preferences({"google_resume": True})
    app = fresh()
    assert not app.exception
    google[0].assert_called_once_with(allow_interactive=False)
    app.run()
    google[0].assert_called_once()
    google[2].create_planner_calendar.assert_not_called()
    app.button(key="google_disconnect").click().run()
    google[0].reset_mock()
    fresh()
    google[0].assert_not_called()


def test_expired_google_auto_resume_offers_explicit_reauthorization_without_loop(google):
    save_preferences({"google_resume": True})
    google[0].side_effect = GoogleConnectionError("Use Authorize Google again")
    app = fresh()
    assert not app.exception and app.error
    app.run()
    google[0].assert_called_once_with(allow_interactive=False)
    assert app.button(key="google_reauthorize")
