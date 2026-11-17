"""For undated work, choose a manual deadline or leave it unscheduled."""

from datetime import date, datetime, time

import streamlit as st

from workload_planner.deadline_planning import DeadlineChoice
from workload_planner.models import Assignment
from workload_planner.display import format_datetime
from workload_planner.resume_ui import preferences, remember

MODES = {"Do not schedule": "skip", "Manual deadline": "manual"}


def deadline_inputs(assignments: list[Assignment], planning_day: date, source: str) -> tuple[dict[str, DeadlineChoice], tuple, bool]:
    undated = [a for a in assignments if a.due_at is None]
    if not undated:
        return {}, (), True
    if planning_day is None:
        st.warning("Enter a planning start date before reviewing undated assignments.")
        return {}, (), False
    choices, signature, ready = {}, [], True
    with st.expander("Review assignments with no deadline", expanded=True):
        st.info("Enter a manual planning deadline or leave each assignment unscheduled. Your planning deadline does not change Canvas.")
        st.caption("Do not schedule keeps the selected assignment visible, with its minutes reported as unscheduled. Deselect it from Assignments to schedule to exclude it from requested workload totals.")
        for assignment in undated:
            aid = assignment.assignment_id
            st.write(f"{assignment.course} — {assignment.title}")
            saved = preferences()["deadline_choices"].get(aid, {})
            default = "Manual deadline" if saved.get("mode") == "manual" else "Do not schedule"
            key = f"deadline_mode_{aid}"
            # An already-open page can still hold a removed week/module label.
            if key in st.session_state and st.session_state[key] not in MODES:
                st.session_state[key] = "Do not schedule"
            mode = MODES[st.selectbox("Planning choice", list(MODES), index=list(MODES).index(default), key=key)]
            day = date.fromisoformat(saved["day"]) if saved else planning_day
            clock = saved.get("clock", "23:59")
            if mode == "manual":
                entered_day = st.date_input("Planning deadline date", value=day, key=f"deadline_day_{aid}", format="MM/DD/YYYY")
                entered_time = st.time_input("Planning deadline time", value=time.fromisoformat(clock), key=f"deadline_clock_{aid}", step=60, format="12h")
                if entered_day is None or entered_time is None:
                    ready = False
                    st.warning("Enter both a date and a time, or choose Do not schedule.")
                else:
                    day, clock = entered_day, entered_time.isoformat(timespec="minutes")
                    choices[aid] = DeadlineChoice(day, clock)
                    st.caption(f"Student planning deadline: {format_datetime(datetime.combine(day, entered_time))} in your selected student timezone.")
            value = {"mode": mode, "day": day.isoformat(), "clock": clock}
            if source == "Canvas":
                remember(deadline_choices={**preferences()["deadline_choices"], aid: value})
            signature.append((aid, tuple(value.items())))
    return choices, tuple(signature), ready
