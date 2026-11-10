"""Google Calendar controls for the single-user app running on this Mac."""

import streamlit as st

from workload_planner.google_auth import GoogleConnectionError, connect_google, forget_google
from workload_planner.google_calendar import CALENDAR_NAME, GoogleCalendarClient
from workload_planner.resume_ui import preferences, remember


def _clear_connection() -> None:
    for key in ("google_connection", "google_calendar_metadata", "google_calendar_choices", "google_extra_calendars", "export_snapshot", "recover_snapshot", "recover_items"):
        st.session_state.pop(key, None)


def _disconnect() -> None:
    remember(google_resume=False)
    _clear_connection()


def google_calendar_controls() -> None:
    """Resume saved consent once; interactive login and calendar writes require clicks."""
    with st.sidebar.expander("Google Calendar", expanded=False):
        st.caption("Local Mac demonstration. Sign in through Google's browser page; no token pasting. Review and approve sessions separately before export.")
        connection = st.session_state.get("google_connection")
        if not st.session_state.get("resume_google_attempted"):
            st.session_state["resume_google_attempted"] = True
            if connection is None and preferences()["google_resume"]:
                try:
                    connection = connect_google(allow_interactive=False)
                    st.session_state["google_connection"] = connection
                except GoogleConnectionError as error:
                    st.error(f"Could not restore Google connection: {error}")
        connect = False
        if connection is None:
            connect = st.button("Connect Google Calendar", key="google_connect")
        reauthorize = st.button("Authorize Google again", key="google_reauthorize", help="Use after expired/revoked consent or to choose a different account. The same account keeps its planner calendar; a different account starts without a selected calendar.")
        if connect or reauthorize:
            _clear_connection()
            connection = None
            try:
                with st.spinner("Complete Google sign-in in the browser that opens (up to 2 minutes)…"):
                    connection = connect_google(reauthorize=reauthorize)
                st.session_state["google_connection"] = connection
                remember(google_resume=True)
                if connection.calendar_id:
                    st.session_state["google_calendar_metadata"] = GoogleCalendarClient(connection).check_planner_calendar()
            except GoogleConnectionError as error:
                st.error(str(error))
        if connection is not None:
            st.success("Google authorization connected.")
            client = GoogleCalendarClient(connection)
            if connection.calendar_id:
                if st.button("Check planner calendar access", key="google_check_calendar"):
                    try:
                        st.session_state["google_calendar_metadata"] = client.check_planner_calendar()
                        st.success("Planner calendar is accessible.")
                    except GoogleConnectionError as error:
                        st.session_state.pop("google_calendar_metadata", None)
                        st.error(str(error))
            elif connection.creation_pending:
                st.warning("A previous calendar creation has an uncertain result. Check Google Calendar before continuing; automatic creation retry is blocked.")
                calendar_id = st.text_input("Planner calendar ID (Calendar settings → Integrate calendar)", key="google_recovery_id")
                if st.button("Recover planner calendar", key="google_recover_calendar"):
                    try:
                        st.session_state["google_calendar_metadata"] = client.recover_calendar(calendar_id)
                    except GoogleConnectionError as error:
                        st.error(str(error))
            else:
                st.caption(f'The next action creates a separate calendar named "{CALENDAR_NAME}" in the account you authorized. It does not create study events.')
                if st.button("Create planner calendar", key="google_create_calendar"):
                    try:
                        st.session_state["google_calendar_metadata"] = client.create_planner_calendar(st.session_state["student_timezone"].strip())
                        st.success("Dedicated planner calendar created and selected.")
                    except GoogleConnectionError as error:
                        st.error(str(error))
            metadata = st.session_state.get("google_calendar_metadata")
            if metadata:
                st.caption(f"Planner calendar: {metadata.get('summary', CALENDAR_NAME)}")
            st.button("Disconnect Google Calendar", key="google_disconnect", on_click=_disconnect)
        if st.button("Forget saved Google authorization", key="google_forget"):
            try:
                forget_google()
                _disconnect()
                st.rerun()
            except GoogleConnectionError as error:
                st.error(str(error))
        st.caption("After connecting, reloads restore saved authorization without opening sign-in. Disconnect stops automatic reconnect; Forget also removes the local Keychain record. Neither deletes calendars. Expired/revoked consent may require Authorize Google again.")
