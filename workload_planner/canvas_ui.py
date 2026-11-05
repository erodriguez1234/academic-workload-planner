"""Streamlit-only Canvas controls; network and conversion stay separate."""

import streamlit as st

from workload_planner.canvas_client import CanvasClient, CanvasClientError
from workload_planner.canvas_import import import_courses
from workload_planner.models import Assignment

DEFAULT_CANVAS_SITE = "https://cilearn.csuci.edu"


def clear_canvas() -> None:
    """Drop credentials, private imports, and Canvas-specific widget state."""
    for key in list(st.session_state):
        if key.startswith("canvas_") or key.startswith("minutes_canvas:"):
            del st.session_state[key]
    st.session_state["result"] = None
    st.session_state["result_signature"] = None


def _clear_snapshot() -> None:
    """A refresh must never leave an old import looking current."""
    for key in ("canvas_snapshot", "canvas_imported_courses", "canvas_assignment_ids"):
        st.session_state.pop(key, None)
    st.session_state["result"] = None
    st.session_state["result_signature"] = None


def canvas_assignment_inputs() -> list[Assignment]:
    """Fetch only on explicit buttons; return the student's selected workload."""
    st.subheader("Canvas import (read-only)")
    st.caption("Load courses, choose courses, then import assignments. Nothing is changed in Canvas.")
    site = st.text_input(
        "Canvas site URL", value=DEFAULT_CANVAS_SITE, key="canvas_base_url",
        help="Use your school's HTTPS Canvas site root, without /api/v1 or a login path.",
    ).strip().rstrip("/")
    with st.form("canvas_connection", clear_on_submit=True):
        token = st.text_input("Canvas personal access token", type="password", key="canvas_token")
        st.caption("Enter privately here. The connection stays in this browser session's server memory; no credential file is written.")
        connect = st.form_submit_button("Load courses", key="canvas_connect")
    if connect:
        _clear_snapshot()
        for key in ("canvas_client", "canvas_courses", "canvas_site", "canvas_course_ids", "canvas_course_warnings"):
            st.session_state.pop(key, None)
        try:
            client = CanvasClient(site, token)
            with st.spinner("Loading accessible courses…"):
                records = client.list_courses()
            courses = []
            warnings = []
            seen = set()
            for position, record in enumerate(records, start=1):
                course_id = record.get("id")
                if type(course_id) is not int or course_id <= 0 or course_id in seen:
                    warnings.append(f"Course record {position} has a missing, invalid, or duplicate ID; course access is incomplete.")
                    continue
                name = record.get("name")
                if not isinstance(name, str) or not name.strip():
                    name = f"Course {course_id} (name unavailable)"
                    warnings.append(f"Course {course_id}: name unavailable; Canvas may restrict access. You can attempt an import.")
                courses.append({"id": course_id, "name": name})
                seen.add(course_id)
            st.session_state.update({
                "canvas_client": client, "canvas_courses": courses,
                "canvas_site": site, "canvas_course_warnings": warnings,
            })
        except (CanvasClientError, ValueError) as error:
            st.error(f"Could not load Canvas courses: {error}")

    st.button("Disconnect and clear Canvas data", key="canvas_disconnect", on_click=clear_canvas)
    if "canvas_client" not in st.session_state:
        return []
    if site != st.session_state["canvas_site"]:
        st.warning("Canvas site changed. Load courses again to connect to this site.")
        return []
    for warning in st.session_state["canvas_course_warnings"]:
        st.warning(warning)
    courses = st.session_state["canvas_courses"]
    by_id = {course["id"]: course for course in courses}
    if not courses:
        st.info("Canvas returned no accessible courses. Check your enrollment and token permissions.")
        return []
    course_ids = st.multiselect(
        "Courses to import", options=list(by_id), key="canvas_course_ids",
        format_func=lambda course_id: (
            by_id[course_id]["name"] if "name unavailable" in by_id[course_id]["name"]
            else f"{by_id[course_id]['name']} ({course_id})"
        ),
    )
    selection = tuple(sorted(course_ids))
    if st.button("Import assignments", key="canvas_import", disabled=not course_ids):
        _clear_snapshot()
        with st.spinner("Importing every accessible assignment page for the selected courses…"):
            snapshot = import_courses(
                st.session_state["canvas_client"], [by_id[cid] for cid in course_ids], site,
            )
        st.session_state["canvas_snapshot"] = snapshot
        st.session_state["canvas_imported_courses"] = selection
    if "canvas_snapshot" not in st.session_state:
        return []
    if selection != st.session_state["canvas_imported_courses"]:
        st.info("Course selection changed. Click Import assignments to load this selection.")
        return []
    snapshot = st.session_state["canvas_snapshot"]
    st.caption("Import snapshot: no background refresh. Coverage is limited to coursework Canvas exposes through the assignment API for these courses.")
    for warning in snapshot.warnings:
        st.warning(warning)
    if not snapshot.items:
        st.info("No assignments imported. Review any access or conversion warnings above.")
        return []
    st.dataframe([
        {"Assignment": item.assignment.title, "Course": item.assignment.course,
         "Deadline": item.assignment.due_at.isoformat(timespec="minutes") if item.assignment.due_at else "No deadline",
         "Type": item.assignment.assignment_type, "Status": item.status,
         "Assignment ID": item.assignment.assignment_id}
        for item in snapshot.items
    ], hide_index=True, width="stretch")
    st.caption("Only explicit quiz/discussion metadata determines type. Unknown types use the provisional 90-minute fallback. Submitted, graded, excused, and unknown-status work starts unchecked; grading does not guarantee that no further work is needed.")
    by_assignment = {item.assignment.assignment_id: item for item in snapshot.items}
    selected = st.multiselect(
        "Assignments to schedule", options=list(by_assignment),
        default=[item.assignment.assignment_id for item in snapshot.items if item.selected_by_default],
        key="canvas_assignment_ids",
        format_func=lambda assignment_id: (
            f"{by_assignment[assignment_id].assignment.course} — "
            f"{by_assignment[assignment_id].assignment.title} "
            f"[{by_assignment[assignment_id].status}] ({assignment_id.rsplit(':', 1)[-1]})"
        ),
    )
    st.caption("Planning dates initially retain the fixed October sample demo settings. Enter your real planning dates in the sidebar before generating a Canvas schedule.")
    return [by_assignment[assignment_id].assignment for assignment_id in selected]
