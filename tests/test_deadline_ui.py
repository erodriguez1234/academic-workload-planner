"""Undated work is explicitly reviewed; Canvas due dates and attendance are preserved."""
from datetime import date
from unittest.mock import Mock

from streamlit.testing.v1 import AppTest

from tests.test_canvas_ui import canvas, canvas_page, imported, FIRST_ID, APP
from workload_planner.local_preferences import load_preferences


def undated_page(canvas):
    canvas[1].return_value[0]["due_at"]=None
    return imported(canvas_page())



def test_only_manual_or_do_not_schedule_are_offered(canvas):
    app = undated_page(canvas)
    assert app.selectbox(key=f"deadline_mode_{FIRST_ID}").options == ["Do not schedule", "Manual deadline"]
    assert not any(b.key == "load_module_placement" for b in app.button)
    app.button(key="generate").click().run()
    assert not app.exception and not app.error
    result = app.session_state["result"]
    assert not result.sessions
    assert result.unscheduled_work[0].reason == "missing_deadline"
    assert result.unscheduled_work[0].remaining_minutes == 90


def test_switching_back_to_do_not_schedule_invalidates_then_removes_sessions(canvas):
    app = undated_page(canvas)
    app.selectbox(key=f"deadline_mode_{FIRST_ID}").set_value("Manual deadline").run()
    app.date_input(key=f"deadline_day_{FIRST_ID}").set_value(date(2026,11,12)).run()
    app.button(key="generate").click().run()
    assert app.session_state["result"].sessions
    app.selectbox(key=f"deadline_mode_{FIRST_ID}").set_value("Do not schedule").run()
    assert any("Inputs changed" in i.value for i in app.info)
    app.button(key="generate").click().run()
    assert not app.session_state["result"].sessions
    assert load_preferences()["deadline_choices"][FIRST_ID]["mode"] == "skip"


def test_old_module_choices_never_trigger_module_api_calls_on_import(canvas, monkeypatch):
    import json
    from workload_planner import local_preferences
    local_preferences.DEFAULT_PATH.write_text(json.dumps({
        "deadline_choices": {FIRST_ID: {"mode":"module", "day":"2026-11-09", "clock":"23:59", "module":"canvas:canvas.example.edu:42:module:3"}},
        "module_weeks": {"canvas:canvas.example.edu:42:module:3":"2026-11-09"},
    }))
    transport = Mock(side_effect=AssertionError("Module transport must not run"))
    monkeypatch.setattr("workload_planner.canvas_client.CanvasClient._list_records", transport)
    app = undated_page(canvas)
    assert not app.exception and not app.error
    assert app.selectbox(key=f"deadline_mode_{FIRST_ID}").value == "Do not schedule"
    app.button(key="generate").click().run()
    assert not app.exception and not app.session_state["result"].sessions
    transport.assert_not_called()
