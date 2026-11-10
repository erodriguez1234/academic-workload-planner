"""Single-page interface; estimation and scheduling rules stay in their modules."""

from datetime import date, datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import streamlit as st

from workload_planner.availability import (
    WeeklyAvailability, expand_weekly_availability, localize_datetime,
)
from workload_planner.estimator import estimate_duration
from workload_planner.display import format_datetime
from workload_planner.canvas_ui import canvas_assignment_inputs
from workload_planner.loaders import load_assignments
from workload_planner.models import Assignment, DurationEstimate
from workload_planner.scheduling_models import (
    ScheduleResult, SchedulingPreferences,
)
from workload_planner import duration_storage
from workload_planner.planning_defaults import current_planning_dates
from workload_planner.google_ui import google_calendar_controls
from workload_planner.resume_ui import preferences as saved_preferences, remember
from workload_planner.google_auth import GoogleConnectionError
from workload_planner.calendar_export import session_event_id
from workload_planner.calendar_export_ui import calendar_settings, plan_with_google, export_controls, recovery_controls
from workload_planner.deadline_ui import deadline_inputs
from workload_planner.deadline_planning import resolve_tasks, build_reviewed_schedule

DAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")

SAMPLE_PATH = Path(__file__).resolve().parent / "sample_data" / "assignments.json"


def remember_duration(assignment_id: str) -> None:
    """Keep edits outside widget state and save Canvas edits across browser sessions."""
    minutes = st.session_state[f"minutes_{assignment_id}"]
    st.session_state["duration_overrides"][assignment_id] = minutes
    if assignment_id.startswith("canvas:"):
        try:
            duration_storage.save_adjustment(assignment_id, minutes)
        except (OSError, ValueError):
            st.session_state["duration_save_warning"] = "Your duration change is active in this session but could not be saved locally."
        else:
            st.session_state.pop("duration_save_warning", None)


def initialize_planning_source(source: str) -> None:
    """Switch editable date profiles without carrying demo dates into Canvas."""
    if "start_date" not in st.session_state:
        reset_demo([])
    previous = st.session_state.get("planning_source", "Sample data")
    profiles = st.session_state.setdefault("planning_date_profiles", {})
    if source != previous:
        profiles[previous] = tuple(st.session_state[key] for key in ("start_date", "start_time", "end_date"))
        if source not in profiles:
            if source == "Canvas":
                try:
                    profiles[source] = current_planning_dates(st.session_state["student_timezone"])
                except (ZoneInfoNotFoundError, ValueError):
                    profiles[source] = current_planning_dates("America/Los_Angeles")
                    st.session_state["date_reset_error"] = "Enter a valid student timezone before using current dates."
            else:
                profiles[source] = date(2026, 10, 10), time(9), date(2026, 10, 17)
        for key, value in zip(("start_date", "start_time", "end_date"), profiles[source]):
            st.session_state[key] = value
        st.session_state["result"] = None
        st.session_state["result_signature"] = None
    st.session_state["planning_source"] = source


def use_current_dates() -> None:
    """Explicitly refresh the suggested Canvas dates without changing durations."""
    try:
        values = current_planning_dates(st.session_state["student_timezone"])
    except (ZoneInfoNotFoundError, ValueError):
        st.session_state["date_reset_error"] = "Enter a valid student timezone before using current dates."
        return
    for key, value in zip(("start_date", "start_time", "end_date"), values):
        st.session_state[key] = value
    st.session_state.pop("date_reset_error", None)
    st.session_state["result"] = None


def assignment_inputs(
    assignments: list[Assignment], estimates: list[DurationEstimate],
) -> dict[str, int]:
    """Keep original estimates separate from durable Canvas minute preferences."""
    saved = st.session_state.setdefault("duration_overrides", {})
    if any(a.assignment_id.startswith("canvas:") for a in assignments) and not st.session_state.get("canvas_adjustments_loaded"):
        try:
            saved.update(duration_storage.load_adjustments())
        except (OSError, ValueError):
            st.session_state["duration_save_warning"] = "Saved duration adjustments could not be loaded. Review the minutes before planning."
        st.session_state["canvas_adjustments_loaded"] = True
    for estimate in estimates:
        st.session_state.setdefault(f"minutes_{estimate.assignment_id}", saved.get(estimate.assignment_id, estimate.estimated_minutes))
    if "duration_save_warning" in st.session_state:
        st.warning(st.session_state["duration_save_warning"])
    st.subheader("1. Review your workload")
    st.dataframe([
        {"Assignment": assignment.title, "Course": assignment.course,
         "Deadline": format_datetime(assignment.due_at, st.session_state["student_timezone"]),
         "Original estimate (min)": estimate.estimated_minutes,
         "Plan with (min)": st.session_state[f"minutes_{assignment.assignment_id}"]}
        for assignment, estimate in zip(assignments, estimates)
    ], hide_index=True, width="stretch")
    with st.expander("Adjust working minutes"):
        st.caption("Estimates are provisional active-work defaults. Your changes only affect this plan.")
        if st.session_state["planning_source"] == "Canvas":
            st.caption("Canvas minute adjustments are saved privately on this computer and reused after re-import or browser refresh.")
        for assignment, estimate in zip(assignments, estimates):
            st.number_input(
                assignment.title, min_value=1, max_value=100_000, step=5,
                key=f"minutes_{assignment.assignment_id}", help=estimate.explanation,
                on_change=remember_duration, args=(assignment.assignment_id,),
            )
    return {a.assignment_id: st.session_state[f"minutes_{a.assignment_id}"] for a in assignments}


def reset_demo(estimates: list[DurationEstimate]) -> None:
    """Reset only planner inputs/results through a button callback."""
    st.session_state.update({
        "start_date": date(2026, 10, 10), "start_time": time(9),
        "end_date": date(2026, 10, 17), "student_timezone": "America/Los_Angeles",
        "session_limit": 60, "daily_limit": 120, "result": None,
        "result_signature": None,
    })
    for day in range(7):
        st.session_state.update({f"enabled_{day}": True, f"start_{day}": time(18), f"end_{day}": time(20)})
    for estimate in estimates:
        st.session_state[f"minutes_{estimate.assignment_id}"] = estimate.estimated_minutes
        st.session_state.setdefault("duration_overrides", {}).pop(estimate.assignment_id, None)


def planning_inputs(
    estimates: list[DurationEstimate],
) -> tuple[date | None, time | None, date | None, str, int, int]:
    """Render persistent context widgets; validation happens on generation."""
    with st.sidebar:
        st.header("Planning preferences")
        st.caption("Review the explicit dates before generating. Canvas and sample mode keep separate planning dates.")
        st.date_input("Planning start date", key="start_date", format="MM/DD/YYYY")
        st.time_input("Planning start time", key="start_time", step=900, format="12h")
        st.date_input("Planning end date (inclusive)", key="end_date", format="MM/DD/YYYY")
        st.text_input("Student timezone", key="student_timezone", help="An IANA name, such as America/Los_Angeles or UTC.")
        st.number_input("Maximum session (minutes)", min_value=1, max_value=1440, key="session_limit")
        st.number_input("Daily study limit (minutes)", min_value=1, max_value=1440, key="daily_limit")
        if st.session_state["planning_source"] == "Sample data":
            st.button("Reset demo", key="reset_demo", on_click=reset_demo, args=(estimates,))
        else:
            st.button("Use current dates", key="use_current_dates", on_click=use_current_dates)
            if "date_reset_error" in st.session_state:
                st.error(st.session_state["date_reset_error"])
        st.caption("Values last through interactions in this browser session. They are not saved to a database.")
    return (
        st.session_state["start_date"], st.session_state["start_time"],
        st.session_state["end_date"], st.session_state["student_timezone"],
        st.session_state["session_limit"], st.session_state["daily_limit"],
    )


def weekly_inputs() -> tuple[tuple[int, bool, time | None, time | None], ...]:
    """One optional local-time window per weekday for the first interface."""
    st.subheader("2. Choose weekly study time")
    st.caption("One window per day. An end earlier than the start means the next day; equal times are invalid.")
    values = []
    with st.expander("Weekly availability", expanded=True):
        for day, name in enumerate(DAYS):
            columns = st.columns([2, 3, 3])
            with columns[0]:
                enabled = st.checkbox(name, key=f"enabled_{day}")
            with columns[1]:
                start = st.time_input(f"{name} start", key=f"start_{day}", step=900, format="12h")
            with columns[2]:
                end = st.time_input(f"{name} end", key=f"end_{day}", step=900, format="12h")
            values.append((day, enabled, start, end))
    return tuple(values)


def show_result(result: ScheduleResult, assignments: list[Assignment], booked_ids: tuple = ()) -> None:
    """Translate IDs to assignment titles and display existing scheduler outputs."""
    by_id = {assignment.assignment_id: assignment for assignment in assignments}
    requested = sum(task.required_minutes for task in result.tasks)
    scheduled = sum(session.duration_minutes for session in result.sessions)
    remaining = sum(work.remaining_minutes for work in result.unscheduled_work)
    columns = st.columns(3)
    for column, label, value in zip(columns, ("Requested minutes", "Scheduled minutes", "Unscheduled minutes"),
                                    (requested, scheduled, remaining)):
        column.metric(label, value)
    if result.sessions:
        st.dataframe([
            {"Assignment": by_id[session.assignment_id].title,
             "Course": by_id[session.assignment_id].course,
             "Start": format_datetime(session.start_at),
             "End": format_datetime(session.end_at),
             "Minutes": session.duration_minutes,
             "Calendar": "Already booked" if booked_ids and session_event_id(st.session_state["google_connection"], session) in booked_ids else "Proposed"}
            for session in result.sessions
        ], hide_index=True, width="stretch")
    else:
        st.info("No sessions could be scheduled with these inputs. Review the warnings below.")
    for work in result.unscheduled_work:
        st.warning(f"{by_id[work.assignment_id].title} — {work.message}")
    if not result.unscheduled_work:
        st.success("All requested work fits the reviewed deadlines and planning targets.")
    st.caption("The planner fills earliest free time. It does not optimize spacing or insert breaks; unplaced work is not proof that no feasible arrangement exists.")


def main() -> None:
    st.set_page_config(page_title="Academic Workload Planner", page_icon="📚", layout="wide")
    st.title("Academic Workload Planner")
    st.caption("Turn assignment deadlines into manageable study sessions.")
    st.session_state.setdefault("data_source", saved_preferences()["source"])
    source = st.radio("Assignment source", ("Sample data", "Canvas"), key="data_source", horizontal=True)
    remember(source=source)
    initialize_planning_source(source)
    if source == "Canvas":
        assignments = canvas_assignment_inputs()
    else:
        try:
            assignments = load_assignments(SAMPLE_PATH)
        except (OSError, ValueError) as error:
            st.error(f"Could not load the sample assignments: {error}")
            return
    estimates = [estimate_duration(assignment) for assignment in assignments]
    if "start_date" not in st.session_state:
        reset_demo(estimates)
    context = planning_inputs(estimates)
    google_calendar_controls()
    google_enabled, calendar_ids, google_context = calendar_settings(source)
    recovery_controls(calendar_ids)
    if not assignments:
        st.info("Import and select assignments to review estimates and build a schedule.")
        weekly_inputs()
        return
    overrides = assignment_inputs(assignments, estimates)
    deadline_choices, deadline_context, deadlines_ready, assigned_weeks = deadline_inputs(assignments, context[0], source)
    weekly = weekly_inputs()
    signature = (
        source, context, tuple(overrides.items()), weekly, google_context, deadline_context,
        tuple((a.assignment_id, a.title, a.course, a.due_at) for a in assignments),
    )

    st.subheader("3. Generate and review")
    st.caption("The end date limits available study time; assignments outside it are still accounted for.")
    if st.button("Generate schedule", key="generate", type="primary"):
        st.session_state["result"] = None
        st.session_state["result_signature"] = None
        try:
            if not deadlines_ready:
                raise ValueError("Complete the selected deadline/module-week choices before generating, or choose how to plan later to leave those minutes unscheduled.")
            start_date, start_time, end_date, zone_name, session_limit, daily_limit = context
            try:
                zone = ZoneInfo(zone_name.strip())
            except (ZoneInfoNotFoundError, ValueError) as error:
                raise ValueError("Unknown timezone. Enter an IANA name such as America/Los_Angeles or UTC.") from error
            if start_date is None or end_date is None or start_time is None:
                raise ValueError("Enter both planning horizon dates and a planning start time.")
            planning_start = localize_datetime(datetime.combine(start_date, start_time), zone)
            rules = []
            for day, enabled, start, end in weekly:
                if enabled:
                    try:
                        rules.append(WeeklyAvailability(day, start, end))
                    except (TypeError, ValueError) as error:
                        raise ValueError(f"{DAYS[day]}: {error}") from error
            periods = expand_weekly_availability(rules, start_date, end_date, zone)
            preferences = SchedulingPreferences(planning_start, zone, session_limit, daily_limit)
            horizon_end = localize_datetime(datetime.combine(end_date + timedelta(days=1), time.min), zone)
            tasks, target_weeks = resolve_tasks(assignments, overrides, deadline_choices, zone, horizon_end=horizon_end)
            booked_ids = ()
            if google_enabled:
                result, booked_ids = plan_with_google(tasks, periods, preferences, horizon_end, calendar_ids, target_weeks, assigned_weeks)
            else:
                result = build_reviewed_schedule(tasks, periods, preferences, target_weeks, assigned_weeks=assigned_weeks)
            st.session_state["result_booked_ids"] = booked_ids
            st.session_state["result"] = result
            st.session_state["result_signature"] = signature
            if not periods:
                st.warning("No study windows fall within this planning horizon. All requested minutes are reported below.")
        except (TypeError, ValueError, GoogleConnectionError) as error:
            st.error(f"Could not generate the plan: {error}")

    result = st.session_state["result"]
    if result is not None:
        if signature != st.session_state["result_signature"]:
            st.info("Inputs changed. Generate a new schedule to see updated sessions and warnings.")
        else:
            st.caption(f"Session times use {context[3]}; timezone labels are shown in the table.")
            booked_ids = st.session_state.get("result_booked_ids", ())
            show_result(result, assignments, booked_ids)
            export_controls(result, assignments, calendar_ids, google_enabled, booked_ids)


if __name__ == "__main__":
    main()
