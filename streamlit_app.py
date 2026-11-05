"""Single-page interface; estimation and scheduling rules stay in their modules."""

from datetime import date, datetime, time
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import streamlit as st

from workload_planner.availability import (
    WeeklyAvailability, expand_weekly_availability, localize_datetime,
)
from workload_planner.estimator import estimate_duration
from workload_planner.canvas_ui import canvas_assignment_inputs
from workload_planner.loaders import load_assignments
from workload_planner.models import Assignment, DurationEstimate
from workload_planner.scheduler import build_schedule
from workload_planner.scheduling_models import (
    ScheduleResult, SchedulingPreferences, SchedulingTask,
)

DAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")

SAMPLE_PATH = Path(__file__).resolve().parent / "sample_data" / "assignments.json"


def assignment_inputs(
    assignments: list[Assignment], estimates: list[DurationEstimate],
) -> dict[str, int]:
    """Keep original estimates separate from session-local student adjustments."""
    for estimate in estimates:
        st.session_state.setdefault(f"minutes_{estimate.assignment_id}", estimate.estimated_minutes)
    st.subheader("1. Review your workload")
    st.dataframe([
        {"Assignment": assignment.title, "Course": assignment.course,
         "Deadline": assignment.due_at.isoformat(timespec="minutes") if assignment.due_at else "No deadline",
         "Original estimate (min)": estimate.estimated_minutes,
         "Plan with (min)": st.session_state[f"minutes_{assignment.assignment_id}"]}
        for assignment, estimate in zip(assignments, estimates)
    ], hide_index=True, width="stretch")
    with st.expander("Adjust working minutes"):
        st.caption("Estimates are provisional active-work defaults. Your changes only affect this plan.")
        for assignment, estimate in zip(assignments, estimates):
            st.number_input(
                assignment.title, min_value=1, max_value=100_000, step=5,
                key=f"minutes_{assignment.assignment_id}", help=estimate.explanation,
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


def planning_inputs(
    estimates: list[DurationEstimate],
) -> tuple[date | None, time | None, date | None, str, int, int]:
    """Render persistent context widgets; validation happens on generation."""
    with st.sidebar:
        st.header("Planning preferences")
        st.caption("Use the demo dates or enter your own planning horizon.")
        st.date_input("Planning start date", key="start_date")
        st.time_input("Planning start time", key="start_time", step=900)
        st.date_input("Planning end date (inclusive)", key="end_date")
        st.text_input("Student timezone", key="student_timezone", help="An IANA name, such as America/Los_Angeles or UTC.")
        st.number_input("Maximum session (minutes)", min_value=1, max_value=1440, key="session_limit")
        st.number_input("Daily study limit (minutes)", min_value=1, max_value=1440, key="daily_limit")
        st.button("Reset demo", key="reset_demo", on_click=reset_demo, args=(estimates,))
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
                start = st.time_input(f"{name} start", key=f"start_{day}", step=900)
            with columns[2]:
                end = st.time_input(f"{name} end", key=f"end_{day}", step=900)
            values.append((day, enabled, start, end))
    return tuple(values)


def show_result(result: ScheduleResult, assignments: list[Assignment]) -> None:
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
             "Start": session.start_at.isoformat(sep=" ", timespec="minutes"),
             "End": session.end_at.isoformat(sep=" ", timespec="minutes"),
             "Minutes": session.duration_minutes}
            for session in result.sessions
        ], hide_index=True, width="stretch")
    else:
        st.info("No sessions could be scheduled with these inputs. Review the warnings below.")
    for work in result.unscheduled_work:
        st.warning(f"{by_id[work.assignment_id].title} — {work.message}")
    if not result.unscheduled_work:
        st.success("All requested work was scheduled before its deadlines.")
    st.caption("The planner fills earliest free time. It does not optimize spacing or insert breaks; unplaced work is not proof that no feasible arrangement exists.")


def main() -> None:
    st.set_page_config(page_title="Academic Workload Planner", page_icon="📚", layout="wide")
    st.title("Academic Workload Planner")
    st.caption("Turn assignment deadlines into manageable study sessions.")
    source = st.radio("Assignment source", ("Sample data", "Canvas"), key="data_source", horizontal=True)
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
    if not assignments:
        st.info("Import and select assignments to review estimates and build a schedule.")
        weekly_inputs()
        return
    overrides = assignment_inputs(assignments, estimates)
    weekly = weekly_inputs()
    signature = (
        source, context, tuple(overrides.items()), weekly,
        tuple((a.assignment_id, a.title, a.course, a.due_at) for a in assignments),
    )

    st.subheader("3. Generate and review")
    st.caption("The end date limits available study time; assignments outside it are still accounted for.")
    if st.button("Generate schedule", key="generate", type="primary"):
        st.session_state["result"] = None
        st.session_state["result_signature"] = None
        try:
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
            tasks = [SchedulingTask(a.assignment_id, overrides[a.assignment_id], a.due_at) for a in assignments]
            result = build_schedule(tasks, periods, preferences)
            st.session_state["result"] = result
            st.session_state["result_signature"] = signature
            if not periods:
                st.warning("No study windows fall within this planning horizon. All requested minutes are reported below.")
        except (TypeError, ValueError) as error:
            st.error(f"Could not generate the plan: {error}")

    result = st.session_state["result"]
    if result is not None:
        if signature != st.session_state["result_signature"]:
            st.info("Inputs changed. Generate a new schedule to see updated sessions and warnings.")
        else:
            st.caption(f"Session times use {context[3]}; offsets are shown in the table.")
            show_result(result, assignments)


if __name__ == "__main__":
    main()
