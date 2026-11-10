"""Explicit busy-time reads, session preview, approval, and export controls."""

from datetime import datetime
from collections.abc import Sequence

import streamlit as st

from workload_planner.calendar_export import (
    ExportItem, ExportLedger, ExportRow, connection_binding, export_preview, fetch_booked_sessions,
    preview_export, session_event_id, unfinished_items,
)
from workload_planner.deadline_planning import build_reviewed_schedule
from workload_planner.display import format_datetime
from workload_planner.google_auth import GoogleConnectionError
from workload_planner.google_calendar import GoogleCalendarClient
from workload_planner.models import Assignment
from workload_planner.scheduling_models import AvailabilityPeriod, ScheduleResult, SchedulingPreferences, SchedulingTask


def calendar_settings(source: str) -> tuple:
    connection = st.session_state.get("google_connection")
    if connection is None:
        return False, (), ()
    with st.sidebar.expander("Calendar availability"):
        enabled = st.checkbox("Avoid Google Calendar busy times", value=source == "Canvas", key=f"respect_google_busy_{source}")
        st.caption("Your primary calendar and the planner calendar are checked. Only Busy events block time, including recurring and all-day events. Reads happen when you generate or preview/export.")
        if st.button("Load other calendars", key="load_conflict_calendars"):
            try:
                st.session_state["google_calendar_choices"] = GoogleCalendarClient(connection).list_calendars()
            except GoogleConnectionError as error:
                st.error(str(error))
        choices = {c["id"]: c.get("summary", c["id"]) for c in st.session_state.get("google_calendar_choices", []) if not c.get("primary") and c["id"] != connection.calendar_id}
        extra = st.multiselect("Other calendars to check", choices, format_func=choices.get, key="google_extra_calendars")
    ids = tuple(sorted({"primary", *extra}))
    context = (enabled, ids, connection.client_id, connection.subject, connection.calendar_id, connection.marker)
    return enabled, ids, context


def plan_with_google(
    tasks: list[SchedulingTask], periods: Sequence[AvailabilityPeriod], preferences: SchedulingPreferences,
    horizon_end: datetime, calendar_ids: tuple[str, ...], target_weeks: dict | None = None, assigned_weeks: dict | None = None,
) -> tuple[ScheduleResult, tuple[str, ...]]:
    connection = st.session_state["google_connection"]
    client = GoogleCalendarClient(connection)
    ledger = ExportLedger()
    booked = fetch_booked_sessions(client, tasks, preferences.planning_start, horizon_end, ledger) if connection.calendar_id else ()
    busy = client.busy_periods(list(calendar_ids), preferences.planning_start, horizon_end)
    result = build_reviewed_schedule(tasks, periods, preferences, target_weeks or {}, busy=busy, booked=booked, assigned_weeks=assigned_weeks)
    return result, tuple(session_event_id(connection, s) for s in booked)


def _rows(rows: Sequence[ExportRow]) -> list[dict]:
    return [{"Assignment": r.item.title, "Start": format_datetime(r.item.session.start_at),
             "End": format_datetime(r.item.session.end_at), "Minutes": r.item.session.duration_minutes,
             "Status": r.status, "Details": r.message} for r in rows]


def _review(items: tuple[ExportItem, ...], calendar_ids: tuple[str, ...], prefix: str) -> None:
    connection = st.session_state["google_connection"]
    client, ledger = GoogleCalendarClient(connection), ExportLedger()
    context = (connection_binding(connection), calendar_ids, items)
    saved = st.session_state.get(f"{prefix}_snapshot")
    if saved is not None and saved[0] != context:
        st.session_state.pop(f"{prefix}_snapshot", None)
        st.session_state[f"{prefix}_approve"] = False
        saved = None
    if st.button("Preview selected sessions" if prefix == "export" else "Preview unfinished exports", key=f"{prefix}_preview", disabled=not items):
        st.session_state.pop(f"{prefix}_snapshot", None)
        st.session_state[f"{prefix}_approve"] = False
        try:
            preview = preview_export(client, items, calendar_ids, ledger)
            saved = (context, preview)
            st.session_state[f"{prefix}_snapshot"] = saved
        except GoogleConnectionError as error:
            saved = None
            st.error(str(error))
    if saved is None:
        return
    preview = saved[1]
    st.dataframe(_rows(preview.rows), hide_index=True, width="stretch")
    blocked = any(r.status not in ("ready", "already present") for r in preview.rows)
    if blocked:
        st.warning("Some sessions have a conflict or require review. Regenerate for new busy times; changed or unfinished planner events need review. Only ready sessions can be sent.")
    approved = st.checkbox("I reviewed these sessions and approve adding the ready sessions to my planner calendar.", key=f"{prefix}_approve")
    if st.button("Export approved sessions", key=f"{prefix}_send", disabled=not approved or not any(r.status == "ready" for r in preview.rows)):
        try:
            rows = export_preview(client, preview, calendar_ids, ledger)
            st.dataframe(_rows(rows), hide_index=True, width="stretch")
            if any(r.status not in ("exported", "already present") for r in rows):
                st.warning("Export stopped or skipped some sessions. Check each result. Use Review unfinished exports for uncertain results before generating a replacement plan.")
            else:
                st.success("Approved sessions are in the planner calendar. Existing sessions were not duplicated.")
            # Consume approval; another attempt requires a fresh preview.
            st.session_state.pop(f"{prefix}_snapshot", None)
        except GoogleConnectionError as error:
            st.error(str(error))


def recovery_controls(calendar_ids: tuple[str, ...]) -> None:
    connection = st.session_state.get("google_connection")
    if connection is None or not connection.calendar_id:
        return
    with st.expander("Review unfinished exports"):
        st.caption("Recover a previously approved attempt after a timeout or restart using the same event IDs. This never moves or deletes events.")
        if st.button("Review unfinished exports", key="recover_load"):
            try:
                st.session_state["recover_items"] = (connection_binding(connection), unfinished_items(connection, ExportLedger()))
            except GoogleConnectionError as error:
                st.error(str(error))
        stored = st.session_state.get("recover_items")
        if stored and stored[0] == connection_binding(connection):
            if not stored[1]:
                st.info("No unfinished exports were recorded for this calendar.")
            _review(stored[1], calendar_ids, "recover")


def export_controls(
    result: ScheduleResult, assignments: list[Assignment], calendar_ids: tuple[str, ...],
    enabled: bool, booked_ids: tuple[str, ...],
) -> None:
    st.subheader("4. Review and export to Google Calendar")
    connection = st.session_state.get("google_connection")
    if connection is None or not connection.calendar_id:
        st.info("Connect Google and create/check its dedicated planner calendar to export sessions.")
        return
    if not enabled:
        st.info("Enable Google Calendar busy-time checks and generate again before exporting.")
        return
    by_id = {a.assignment_id: a for a in assignments}
    options = {session_event_id(connection, s): ExportItem(s, by_id[s.assignment_id].title, by_id[s.assignment_id].course) for s in result.sessions if session_event_id(connection, s) not in booked_ids}
    st.caption("Select proposed sessions explicitly. Already booked sessions count toward the workload and daily limit. Export rechecks busy time and only adds events to the planner calendar; no events are moved or deleted.")
    selected = st.multiselect("Sessions to export", options, format_func=lambda key: f"{options[key].title} — {format_datetime(options[key].session.start_at)} ({options[key].session.duration_minutes} min)", key="export_sessions")
    _review(tuple(options[key] for key in selected), calendar_ids, "export")
