"""Run the real page and interact with its widgets without a browser server."""

from datetime import date, time
from pathlib import Path

from streamlit.testing.v1 import AppTest

APP = Path(__file__).resolve().parents[1] / "streamlit_app.py"


def page() -> AppTest:
    return AppTest.from_file(str(APP), default_timeout=15).run()


def test_page_displays_sample_assignments_and_original_estimates() -> None:
    app = page()
    assert not app.exception
    assert app.title[0].value == "Academic Workload Planner"
    table = app.dataframe[0].value
    assert len(table) == 4
    assert table["Original estimate (min)"].tolist() == [30, 180, 60, 180]


def test_dates_and_times_are_readable_in_tables_and_controls() -> None:
    app = page()
    assert all(widget.proto.format == "12h" for widget in app.time_input)
    assert all(widget.proto.format == "MM/DD/YYYY" for widget in app.date_input)
    deadlines = app.dataframe[0].value["Deadline"].tolist()
    assert "No deadline" in deadlines
    assert all(value == "No deadline" or ("October " in value and ("AM" in value or "PM" in value)) for value in deadlines)
    app.button(key="generate").click().run()
    sessions = app.dataframe[1].value
    assert sessions.iloc[0]["Start"] == "October 10, 2026 6:00PM PDT"
    assert sessions.iloc[0]["End"] == "October 10, 2026 6:30PM PDT"


def test_adjusted_minutes_persist_without_overwriting_original_estimate() -> None:
    app = page()
    app.number_input(key="minutes_sample-quiz-1").set_value(75).run()
    assert not app.exception
    assert app.number_input(key="minutes_sample-quiz-1").value == 75
    assert app.dataframe[0].value["Original estimate (min)"].tolist()[0] == 30
    app.run()
    assert app.number_input(key="minutes_sample-quiz-1").value == 75


def test_generates_sample_schedule_and_reports_undated_work() -> None:
    app = page()
    app.button(key="generate").click().run()
    assert not app.exception and not app.error
    result = app.session_state["result"]
    assert sum(session.duration_minutes for session in result.sessions) == 390
    assert sum(work.remaining_minutes for work in result.unscheduled_work) == 60
    assert any("no deadline was supplied" in warning.value for warning in app.warning)
    assert len(app.dataframe) == 2


def test_adjustment_reaches_scheduler_and_survives_other_interactions() -> None:
    app = page()
    app.number_input(key="minutes_sample-quiz-1").set_value(75).run()
    app.number_input(key="session_limit").set_value(45).run()
    app.button(key="generate").click().run()
    assert not app.exception
    task = next(t for t in app.session_state["result"].tasks if t.assignment_id == "sample-quiz-1")
    assert task.required_minutes == 75
    assert app.number_input(key="minutes_sample-quiz-1").value == 75
    assert app.number_input(key="session_limit").value == 45


def test_changed_inputs_hide_stale_schedule_until_regenerated() -> None:
    app = page()
    app.button(key="generate").click().run()
    app.number_input(key="daily_limit").set_value(30).run()
    assert not app.exception
    assert any("Inputs changed" in message.value for message in app.info)
    assert len(app.dataframe) == 1
    app.button(key="generate").click().run()
    assert len(app.dataframe) == 2
    assert sum(s.duration_minutes for s in app.session_state["result"].sessions) < 390


def test_invalid_timezone_shows_feedback_and_keeps_adjustments() -> None:
    app = page()
    app.number_input(key="minutes_sample-quiz-1").set_value(75).run()
    app.text_input(key="student_timezone").set_value("Not/AZone").run()
    app.button(key="generate").click().run()
    assert not app.exception
    assert any("timezone" in error.value.lower() for error in app.error)
    assert app.number_input(key="minutes_sample-quiz-1").value == 75


def test_invalid_horizon_shows_feedback_instead_of_traceback() -> None:
    app = page()
    app.date_input(key="end_date").set_value(date(2026, 10, 9)).run()
    app.button(key="generate").click().run()
    assert not app.exception
    assert any("horizon" in error.value.lower() for error in app.error)


def test_equal_weekly_times_are_rejected_with_clear_feedback() -> None:
    app = page()
    app.time_input(key="end_0").set_value(time(18)).run()
    app.button(key="generate").click().run()
    assert not app.exception
    assert any("differ" in error.value for error in app.error)


def test_no_selected_days_reports_all_requested_minutes() -> None:
    app = page()
    for day in range(7):
        app.checkbox(key=f"enabled_{day}").uncheck()
    app.run()
    app.button(key="generate").click().run()
    assert not app.exception
    result = app.session_state["result"]
    assert result.sessions == ()
    assert sum(work.remaining_minutes for work in result.unscheduled_work) == 450


def test_reset_demo_restores_inputs_and_clears_old_results() -> None:
    app = page()
    app.number_input(key="minutes_sample-quiz-1").set_value(75).run()
    app.button(key="generate").click().run()
    app.button(key="reset_demo").click().run()
    assert not app.exception
    assert app.number_input(key="minutes_sample-quiz-1").value == 30
    assert app.session_state["result"] is None


def test_overlapping_overnight_days_are_rejected_in_page() -> None:
    app = page()
    app.time_input(key="start_0").set_value(time(23)).run()
    app.time_input(key="end_0").set_value(time(19)).run()
    app.button(key="generate").click().run()
    assert not app.exception
    assert any("overlap" in error.value.lower() for error in app.error)


def test_can_correct_invalid_input_and_generate_without_losing_values() -> None:
    app = page()
    app.number_input(key="minutes_sample-quiz-1").set_value(75).run()
    app.text_input(key="student_timezone").set_value("Not/AZone").run()
    app.button(key="generate").click().run()
    app.text_input(key="student_timezone").set_value("America/Los_Angeles").run()
    app.button(key="generate").click().run()
    assert not app.exception and not app.error
    assert app.number_input(key="minutes_sample-quiz-1").value == 75
    assert app.session_state["result"] is not None


def test_ambiguous_planning_start_shows_clock_change_feedback() -> None:
    app = page()
    app.date_input(key="start_date").set_value(date(2026, 11, 1)).run()
    app.date_input(key="end_date").set_value(date(2026, 11, 2)).run()
    app.time_input(key="start_time").set_value(time(1, 30)).run()
    app.button(key="generate").click().run()
    assert not app.exception
    assert any("clock change" in error.value for error in app.error)


def test_past_sample_deadlines_are_reported_for_a_later_planning_date() -> None:
    app = page()
    app.date_input(key="start_date").set_value(date(2026, 10, 21)).run()
    app.date_input(key="end_date").set_value(date(2026, 10, 28)).run()
    app.button(key="generate").click().run()
    assert not app.exception
    result = app.session_state["result"]
    assert result.sessions == ()
    assert len(result.unscheduled_work) == 4
    assert sum(work.remaining_minutes for work in result.unscheduled_work) == 450
    assert sum(work.reason == "deadline_not_after_start" for work in result.unscheduled_work) == 3
