"""Review missing deadlines and explicitly map Canvas modules to study weeks."""

from datetime import date, datetime, time, timedelta

import streamlit as st

from workload_planner.canvas_modules import load_module_catalog
from workload_planner.deadline_planning import DeadlineChoice
from workload_planner.models import Assignment
from workload_planner.display import format_datetime
from workload_planner.resume_ui import preferences, remember

MODES = {"Choose how to plan": "skip", "Manual deadline": "manual",
         "After dated work (choose week)": "week", "After dated work (module week)": "module"}


def _modules(undated: list[Assignment]) -> tuple:
    if "canvas_snapshot" not in st.session_state:
        return ()
    if st.button("Load module placement from Canvas", key="load_module_placement"):
        courses = [c for c in st.session_state["canvas_courses"] if c["id"] in st.session_state["canvas_imported_courses"]]
        with st.spinner("Reading module and item pages (read-only)…"):
            st.session_state["canvas_module_catalog"] = load_module_catalog(
                st.session_state["canvas_client"], courses, st.session_state["canvas_snapshot"].items, st.session_state["canvas_site"],
            )
    catalog = st.session_state.get("canvas_module_catalog")
    if catalog is None:
        st.caption("Load module placement to see where Canvas lists this work. Module names and unlock dates are not assumed deadlines.")
        return ()
    for warning in catalog.warnings:
        st.warning(warning)
    selected = {a.assignment_id for a in undated}
    modules = tuple(m for m in catalog.modules if selected.intersection(m.assignment_ids))
    if not modules:
        st.info("No reliable module links found for the selected undated assignments. Enter a deadline or choose a week manually.")
    for module in modules:
        saved = preferences()["module_weeks"].get(module.key)
        day = st.date_input(f"Week starting Monday — {module.course} / {module.name}", value=date.fromisoformat(saved) if saved else None,
                            key=f"module_week_{module.key}", format="MM/DD/YYYY")
        weeks = dict(preferences()["module_weeks"])
        if day is None:
            weeks.pop(module.key, None)
        elif day.weekday() != 0:
            st.warning("Choose a Monday for this module’s week.")
            weeks.pop(module.key, None)
        else:
            weeks[module.key] = day.isoformat()
        remember(module_weeks=weeks)
    return modules


def deadline_inputs(assignments: list[Assignment], planning_day: date, source: str) -> tuple[dict[str, DeadlineChoice], tuple, bool, dict[str, date]]:
    undated = [a for a in assignments if a.due_at is None]
    if not undated:
        return {}, (), True, {}
    if planning_day is None:
        st.warning("Enter a planning start date before reviewing undated assignments.")
        return {}, (), False, {}
    choices, signature, ready = {}, [], True
    with st.expander("Review assignments with no deadline", expanded=True):
        st.warning("Some selected assignments have no deadline. Enter a planning deadline or confirm a week. These are your planning targets, not professor-provided due dates.")
        st.caption("Selected dated work reserves capacity first. Week-based work waits until that week’s last dated-work day/session, then uses remaining study time, including later weeks within your planning horizon. Module mappings identify the reference week; otherwise dated work is grouped by its due-date week. If related dated work is still unscheduled, week-based work waits too. Unreviewed work remains explicitly unscheduled.")
        modules = _modules(undated) if source == "Canvas" else ()
        for assignment in undated:
            aid = assignment.assignment_id
            st.write(f"{assignment.course} — {assignment.title}")
            saved = preferences()["deadline_choices"].get(aid, {})
            mode_label = next((label for label, value in MODES.items() if value == saved.get("mode")), "Choose how to plan")
            mode = MODES[st.selectbox("Planning choice", list(MODES), index=list(MODES).index(mode_label), key=f"deadline_mode_{aid}")]
            day = date.fromisoformat(saved["day"]) if saved else planning_day
            clock = saved.get("clock", "23:59")
            module_key = saved.get("module", "")
            if mode in ("manual", "week"):
                day = st.date_input("Planning deadline date" if mode == "manual" else "A date in the week this work belongs to",
                                    value=day, key=f"deadline_day_{aid}", format="MM/DD/YYYY")
                if day is None:
                    ready = False
                    day = planning_day
                if mode == "manual":
                    clock = st.time_input("Planning deadline time", value=time.fromisoformat(clock), key=f"deadline_clock_{aid}", step=60, format="12h").isoformat(timespec="minutes")
                    st.caption(f"Student planning deadline: {format_datetime(datetime.combine(day, time.fromisoformat(clock)))} in your selected student timezone.")
                choices[aid] = DeadlineChoice(mode, day, clock)
                if mode == "week":
                    monday = day - timedelta(days=day.weekday())
                    st.caption(f"Assumed planning week: {monday:%B %d, %Y} through {monday + timedelta(days=6):%B %d, %Y}. Lower priority than dated work.")
            elif mode == "module":
                linked = {m.key: m for m in modules if aid in m.assignment_ids}
                options = ["", *linked]
                default = module_key if module_key in linked else (next(iter(linked)) if len(linked) == 1 else "")
                module_key = st.selectbox("Module for this assignment", options, index=options.index(default), key=f"deadline_module_{aid}",
                                          format_func=lambda key: f"{linked[key].course} / {linked[key].name}" if key else "Select a module")
                week = preferences()["module_weeks"].get(module_key)
                if not week:
                    st.warning("Load module placement, select the intended module, and confirm its Monday week start before generating.")
                    ready = False
                else:
                    day = date.fromisoformat(week)
                    choices[aid] = DeadlineChoice("week", day)
                    st.caption(f"Assumed module week: {day:%B %d, %Y} through {day + timedelta(days=6):%B %d, %Y}.")
            value = {"mode": mode, "day": day.isoformat(), "clock": clock, "module": module_key}
            if aid.startswith("canvas:"):
                remember(deadline_choices={**preferences()["deadline_choices"], aid: value})
            signature.append((aid, tuple(value.items())))
    memberships = {}
    ambiguous = set()
    for module in modules:
        week = preferences()["module_weeks"].get(module.key)
        if week:
            for aid in module.assignment_ids:
                day = date.fromisoformat(week)
                if aid in memberships and memberships[aid] != day:
                    ambiguous.add(aid)
                memberships[aid] = day
    for aid in ambiguous:
        memberships.pop(aid, None)
    if ambiguous:
        st.warning("Some assignments appear in modules mapped to different weeks. Choose the intended module for undated work; dated work uses its due-date week when module placement is ambiguous.")
    return choices, (tuple(signature), tuple(sorted(memberships.items()))), ready, memberships
