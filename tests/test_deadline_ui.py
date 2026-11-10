"""Undated work is explicitly reviewed; Canvas due dates and attendance are preserved."""
from datetime import date
from unittest.mock import Mock

from streamlit.testing.v1 import AppTest

from tests.test_canvas_ui import canvas, canvas_page, imported, FIRST_ID, APP
from workload_planner.local_preferences import load_preferences


def undated_page(canvas):
    canvas[1].return_value[0]["due_at"]=None
    return imported(canvas_page())


def test_manual_deadline_schedules_undated_work_and_persists_choice(canvas):
    app=undated_page(canvas)
    app.selectbox(key=f"deadline_mode_{FIRST_ID}").set_value("Manual deadline").run()
    app.date_input(key=f"deadline_day_{FIRST_ID}").set_value(date(2026,11,12)).run()
    app.button(key="generate").click().run()
    assert not app.exception and not app.error
    assert sum(s.duration_minutes for s in app.session_state["result"].sessions)==90
    assert app.session_state["canvas_snapshot"].items[0].assignment.due_at is None
    assert load_preferences()["deadline_choices"][FIRST_ID]["mode"]=="manual"
    refreshed=imported(canvas_page())
    assert refreshed.selectbox(key=f"deadline_mode_{FIRST_ID}").value=="Manual deadline"


def test_week_target_is_confirmed_and_changing_it_hides_old_results(canvas):
    app=undated_page(canvas)
    app.selectbox(key=f"deadline_mode_{FIRST_ID}").set_value("After dated work (choose week)").run()
    app.date_input(key=f"deadline_day_{FIRST_ID}").set_value(date(2026,11,9)).run()
    app.button(key="generate").click().run()
    result=app.session_state["result"]
    assert not app.exception and result.sessions
    assert all(s.start_at.date()>=date(2026,11,9) and s.end_at.date()<=date(2026,11,15) for s in result.sessions)
    app.date_input(key=f"deadline_day_{FIRST_ID}").set_value(date(2026,11,16)).run()
    assert any("Inputs changed" in i.value for i in app.info)


def test_module_week_mapping_drives_the_selected_undated_assignment(canvas,monkeypatch):
    modules=Mock(return_value=[{"id":3,"name":"Module 3"}])
    entries=Mock(return_value=[{"type":"Assignment","content_id":7}])
    monkeypatch.setattr("workload_planner.canvas_client.CanvasClient.list_modules",modules)
    monkeypatch.setattr("workload_planner.canvas_client.CanvasClient.list_module_items",entries)
    app=undated_page(canvas)
    modules.assert_not_called()
    app.button(key="load_module_placement").click().run()
    module_key="canvas:canvas.example.edu:42:module:3"
    app.date_input(key=f"module_week_{module_key}").set_value(date(2026,11,16)).run()
    app.selectbox(key=f"deadline_mode_{FIRST_ID}").set_value("After dated work (module week)").run()
    app.button(key="generate").click().run()
    assert not app.exception and not app.error
    assert app.session_state["result"].sessions[0].start_at.date()>=date(2026,11,16)
    assert load_preferences()["module_weeks"][module_key]=="2026-11-16"
    entries.assert_called_once_with(42,3)


def test_roll_call_never_appears_in_import_table_or_assignment_selector(canvas):
    canvas[1].return_value.append({"id":99,"course_id":42,"name":"Roll Call Attendance","due_at":None})
    app=imported(canvas_page())
    assert not app.exception
    assert "Roll Call Attendance" not in app.dataframe[0].value["Assignment"].tolist()
    assert not any("Roll Call" in value for value in app.multiselect(key="canvas_assignment_ids").options)


def test_unmapped_module_choice_cannot_silently_schedule_current_week(canvas):
    app=undated_page(canvas)
    app.selectbox(key=f"deadline_mode_{FIRST_ID}").set_value("After dated work (module week)").run()
    app.button(key="generate").click().run()
    assert not app.exception and app.error
    assert app.session_state["result"] is None


def test_new_canvas_deadline_overrides_saved_student_choice(canvas):
    app=undated_page(canvas)
    app.selectbox(key=f"deadline_mode_{FIRST_ID}").set_value("Manual deadline").run()
    app.date_input(key=f"deadline_day_{FIRST_ID}").set_value(date(2026,11,19)).run()
    canvas[1].return_value[0]["due_at"]="2026-11-12T22:00:00Z"
    app.button(key="canvas_import").click().run()
    app.button(key="generate").click().run()
    assert not app.exception
    task=next(t for t in app.session_state["result"].tasks if t.assignment_id==FIRST_ID)
    assert task.due_at.day==12
    assert not any(w.key==f"deadline_mode_{FIRST_ID}" for w in app.selectbox)


def test_saved_module_week_is_verified_and_restored_with_a_fresh_import(canvas,monkeypatch):
    modules=Mock(return_value=[{"id":3,"name":"Module 3"}])
    entries=Mock(return_value=[{"type":"Assignment","content_id":7}])
    monkeypatch.setattr("workload_planner.canvas_client.CanvasClient.list_modules",modules)
    monkeypatch.setattr("workload_planner.canvas_client.CanvasClient.list_module_items",entries)
    app=undated_page(canvas)
    app.button(key="load_module_placement").click().run()
    key="canvas:canvas.example.edu:42:module:3"
    app.date_input(key=f"module_week_{key}").set_value(date(2026,11,9)).run()
    app.selectbox(key=f"deadline_mode_{FIRST_ID}").set_value("After dated work (module week)").run()
    modules.reset_mock();entries.reset_mock()
    refreshed=imported(canvas_page())
    refreshed.button(key="generate").click().run()
    assert not refreshed.exception and not refreshed.error
    assert refreshed.session_state["result"].sessions
    modules.assert_called()
    assert refreshed.date_input(key=f"module_week_{key}").value==date(2026,11,9)
