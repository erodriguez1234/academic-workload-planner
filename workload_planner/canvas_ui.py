"""Streamlit-only Canvas controls; network and conversion stay separate."""

import streamlit as st

from workload_planner.canvas_client import CanvasClient, CanvasClientError
from workload_planner.canvas_import import import_courses
from workload_planner.canvas_modules import load_module_catalog
from workload_planner.models import Assignment
from workload_planner.resume_ui import preferences, remember, remember_classes
from workload_planner.display import format_datetime
from workload_planner.credentials import (
    CredentialStoreError, forget_token, load_token, save_token,
)

DEFAULT_CANVAS_SITE = "https://cilearn.csuci.edu"


def clear_canvas() -> None:
    """Drop credentials, private imports, and Canvas-specific widget state."""
    remember(canvas_resume=False)
    for key in list(st.session_state):
        if key.startswith("canvas_") or key.startswith("minutes_canvas:"):
            del st.session_state[key]
    st.session_state["result"] = None
    st.session_state["result_signature"] = None


def _clear_snapshot() -> None:
    """A refresh must never leave an old import looking current."""
    for key in ("canvas_snapshot", "canvas_imported_courses", "canvas_assignment_ids", "canvas_module_catalog"):
        st.session_state.pop(key, None)
    st.session_state["result"] = None
    st.session_state["result_signature"] = None


def forget_saved_token(site: str) -> None:
    """Forget only this site's stored token and clear the active connection."""
    try:
        forget_token(site)
    except (CredentialStoreError, ValueError) as error:
        st.error(str(error))
        return
    clear_canvas()
    st.success("Saved token forgotten. The Canvas connection and imported data were cleared.")


def _load_courses(site: str, token: str) -> None:
    """Validate accessible courses and restore only saved IDs still accessible."""
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
    saved = preferences()["courses"].get(site, [])
    available = {course["id"] for course in courses}
    st.session_state["canvas_course_ids"] = [cid for cid in saved if cid in available]
    missing = set(saved) - available
    if missing:
        st.session_state["canvas_course_warnings"].append(
            f"{len(missing)} saved class(es) are no longer accessible. They were not imported; review your current classes."
        )
    st.session_state["canvas_restore_import"] = bool(st.session_state["canvas_course_ids"])


def canvas_assignment_inputs() -> list[Assignment]:
    """Resume saved classes once per session, or fetch on explicit refresh actions."""
    st.subheader("Canvas import (read-only)")
    st.caption("Choose your current classes once. With a remembered token, reloads reconnect and fetch fresh assignments for those classes. Nothing is changed in Canvas.")
    site = st.text_input(
        "Canvas site URL", value=preferences()["canvas_site"], key="canvas_base_url",
        help="Use your school's HTTPS Canvas site root, without /api/v1 or a login path.",
    ).strip().rstrip("/")
    if not st.session_state.get("resume_canvas_attempted"):
        st.session_state["resume_canvas_attempted"] = True
        if preferences()["canvas_resume"] and site == preferences()["canvas_site"]:
            try:
                token = load_token(site)
                if not token:
                    raise ValueError("No saved token for this Canvas site. Enter a token privately to reconnect.")
                _load_courses(site, token)
            except (CanvasClientError, CredentialStoreError, ValueError) as error:
                st.error(f"Could not restore Canvas: {error}")
    connect = False
    connected = "canvas_client" in st.session_state and site == st.session_state["canvas_site"]
    if not connected:
        with st.form("canvas_connection", clear_on_submit=True):
            token = st.text_input("Canvas personal access token", type="password", key="canvas_token")
            remember_token = st.checkbox("Remember token on this Mac", key="canvas_remember_token")
            st.caption("Leave the token blank to use a previously saved token. Remembering stores it in macOS Keychain; the password field is never prefilled.")
            connect = st.form_submit_button("Load courses", key="canvas_connect")
    if connect:
        _clear_snapshot()
        for key in ("canvas_client", "canvas_courses", "canvas_site", "canvas_course_ids", "canvas_course_warnings"):
            st.session_state.pop(key, None)
        try:
            # Copy/paste often includes an outer newline; don't change the token itself.
            token = token.strip()
            used_saved_token = not token
            if not token:
                token = load_token(site)
                if not token:
                    raise ValueError("No saved token for this Canvas site. Enter a token privately to connect.")
            if any(character.isspace() or not 33 <= ord(character) <= 126 for character in token):
                raise ValueError(
                    "The token contains whitespace or unsupported characters inside it. "
                    "Copy only the token value from Canvas and paste it again."
                )
            _load_courses(site, token)
            resume = used_saved_token
            if remember_token:
                try:
                    save_token(site, token)
                except CredentialStoreError as error:
                    st.session_state["canvas_connection_notice"] = ("warning", str(error))
                else:
                    resume = True
                    st.session_state["canvas_connection_notice"] = (
                        "success", "Token saved in macOS Keychain. Reloads will reconnect and load your saved classes automatically.",
                    )
            remember(canvas_site=site, canvas_resume=resume)
            # Render from connected state so the submitted form is absent from the page.
            st.rerun()
        except (CanvasClientError, CredentialStoreError, ValueError) as error:
            st.error(f"Could not load Canvas courses: {error}")

    if connected:
        st.success("Connected to Canvas.")
    notice = st.session_state.pop("canvas_connection_notice", None)
    if notice is not None:
        level, message = notice
        if level == "warning":
            st.warning(message)
        else:
            st.success(message)
    st.button("Disconnect and clear Canvas data", key="canvas_disconnect", on_click=clear_canvas)
    st.button("Forget saved token", key="canvas_forget_token", on_click=forget_saved_token, args=(site,))
    st.caption("Disconnect clears Canvas data and stops automatic reconnect. Your class choices remain saved. Forget saved token also removes the remembered token for this site. Tokens still expire on the date set in Canvas.")
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
        "Select Classes to Import", options=list(by_id), key="canvas_course_ids",
        on_change=remember_classes,
        format_func=lambda course_id: (
            by_id[course_id]["name"] if "name unavailable" in by_id[course_id]["name"]
            else f"{by_id[course_id]['name']} ({course_id})"
        ),
    )
    selection = tuple(sorted(course_ids))
    restore_import = st.session_state.pop("canvas_restore_import", False)
    if st.button("Import assignments", key="canvas_import", disabled=not course_ids) or (restore_import and course_ids):
        _clear_snapshot()
        with st.spinner("Importing every accessible assignment page for the selected courses…"):
            snapshot = import_courses(
                st.session_state["canvas_client"], [by_id[cid] for cid in course_ids], site,
            )
        st.session_state["canvas_snapshot"] = snapshot
        st.session_state["canvas_imported_courses"] = selection
        if any(preferences()["deadline_choices"].get(item.assignment.assignment_id, {}).get("mode") == "module" for item in snapshot.items if item.assignment.due_at is None):
            with st.spinner("Checking saved module placement…"):
                st.session_state["canvas_module_catalog"] = load_module_catalog(
                    st.session_state["canvas_client"], [by_id[cid] for cid in course_ids], snapshot.items, site,
                )
    if "canvas_snapshot" not in st.session_state:
        return []
    if selection != st.session_state["canvas_imported_courses"]:
        st.info("Course selection changed. Click Import assignments to load this selection.")
        return []
    snapshot = st.session_state["canvas_snapshot"]
    st.caption("Fresh import for this session; use Import assignments to refresh again. Coverage is limited to coursework Canvas exposes through the assignment API for these courses.")
    for warning in snapshot.warnings:
        st.warning(warning)
    if not snapshot.items:
        st.info("No assignments imported. Review any access or conversion warnings above.")
        return []
    st.dataframe([
        {"Assignment": item.assignment.title, "Course": item.assignment.course,
         "Deadline": format_datetime(item.assignment.due_at, st.session_state.get("student_timezone", "America/Los_Angeles")),
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
    st.caption("Review the Canvas planning dates in the sidebar before generating. Use current dates starts a fresh 14-day horizon; work without deadlines or available time is reported explicitly.")
    return [by_assignment[assignment_id].assignment for assignment_id in selected]
