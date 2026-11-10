"""Preference access for Streamlit; no API calls or credentials in this module."""

import streamlit as st

from workload_planner.local_preferences import load_preferences, save_preferences, DEFAULTS


def preferences() -> dict:
    if "local_preferences" not in st.session_state:
        try:
            st.session_state["local_preferences"] = load_preferences()
        except (OSError, ValueError):
            st.session_state["local_preferences"] = {**DEFAULTS, "courses": {}}
            st.warning("Saved planner preferences could not be read. Automatic reconnect is off; existing settings were not overwritten.")
    return st.session_state["local_preferences"]


def remember(**changes: object) -> None:
    current = preferences()
    if all(current.get(key) == value for key, value in changes.items()):
        return
    # Keep the current browser usable even when local storage is unavailable.
    st.session_state["local_preferences"] = {**current, **changes}
    try:
        save_preferences(changes)
    except (OSError, ValueError):
        st.warning("Planner choices could not be saved for reloads. This session still works; existing settings were not overwritten.")


def remember_classes() -> None:
    site = st.session_state["canvas_site"]
    courses = {**preferences()["courses"], site: list(st.session_state["canvas_course_ids"])}
    remember(courses=courses)
