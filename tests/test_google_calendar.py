"""Calendar metadata only: no event APIs, retries, or private live requests."""

from unittest.mock import Mock

import pytest

from workload_planner.google_calendar import GoogleCalendarClient
from workload_planner.google_auth import GoogleConnectionError


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> tuple:
    connection = Mock(calendar_id=None, creation_pending=False, marker="synthetic-marker")
    response = Mock(status_code=200)
    response.json.return_value = {"id": "planner-id", "summary": "Academic Workload Planner"}
    session = Mock()
    session.request.return_value = response
    session.__enter__ = Mock(return_value=session)
    session.__exit__ = Mock(return_value=False)
    monkeypatch.setattr("workload_planner.google_calendar.AuthorizedSession", Mock(return_value=session))
    return GoogleCalendarClient(connection), connection, session, response


def test_calendar_creation_is_explicit_and_saved_before_return(client: tuple) -> None:
    api, connection, session, _ = client
    session.request.assert_not_called()
    result = api.create_planner_calendar("America/Los_Angeles")
    assert result["id"] == "planner-id" and connection.calendar_id == "planner-id"
    call = session.request.call_args
    assert call.args == ("POST", "https://www.googleapis.com/calendar/v3/calendars")
    assert call.kwargs["json"]["summary"] == "Academic Workload Planner"
    assert "synthetic-marker" in call.kwargs["json"]["description"]
    assert connection.persist.call_count == 2  # Pending marker, then resulting ID.


def test_existing_calendar_is_checked_not_created_again(client: tuple) -> None:
    api, connection, session, _ = client
    connection.calendar_id = "planner-id"
    api.create_planner_calendar("UTC")
    assert session.request.call_args.args[0] == "GET"
    assert session.request.call_count == 1


def test_storage_failure_prevents_remote_creation(client: tuple) -> None:
    api, connection, session, _ = client
    connection.persist.side_effect = GoogleConnectionError("Keychain unavailable")
    with pytest.raises(GoogleConnectionError):
        api.create_planner_calendar("UTC")
    session.request.assert_not_called()


def test_uncertain_network_failure_blocks_duplicate_creation_retry(client: tuple) -> None:
    api, connection, session, _ = client
    session.request.side_effect = TimeoutError("private response")
    with pytest.raises(GoogleConnectionError):
        api.create_planner_calendar("UTC")
    assert connection.creation_pending is True
    with pytest.raises(GoogleConnectionError, match="may have succeeded"):
        api.create_planner_calendar("UTC")
    assert session.request.call_count == 1


@pytest.mark.parametrize("status", [401, 403, 404, 429, 500])
def test_api_failures_are_readable_and_do_not_return_private_body(client: tuple, status: int) -> None:
    api, connection, _, response = client
    connection.calendar_id = "planner-id"
    response.status_code = status
    response.text = "synthetic-private-body"
    with pytest.raises(GoogleConnectionError, match=str(status)) as caught:
        api.check_planner_calendar()
    assert "synthetic-private-body" not in str(caught.value)


def test_recovery_checks_ownership_marker_before_selecting_calendar(client: tuple) -> None:
    api, connection, _, response = client
    connection.creation_pending = True
    response.json.return_value = {"id": "planner-id", "description": "Unrelated calendar"}
    with pytest.raises(GoogleConnectionError, match="ownership"):
        api.recover_calendar("planner-id")
    assert connection.calendar_id is None
    response.json.return_value["description"] = "Academic Workload Planner / synthetic-marker"
    assert api.recover_calendar("planner-id")["id"] == "planner-id"


def test_invalid_timezone_never_creates_calendar(client: tuple) -> None:
    api, _, session, _ = client
    with pytest.raises(GoogleConnectionError, match="timezone"):
        api.create_planner_calendar("Not/AZone")
    session.request.assert_not_called()


def test_definitive_permission_rejection_does_not_leave_uncertain_creation(client: tuple) -> None:
    api, connection, _, response = client
    response.status_code = 403
    with pytest.raises(GoogleConnectionError, match="403"):
        api.create_planner_calendar("UTC")
    assert connection.creation_pending is False


def test_successful_creation_with_failed_final_save_does_not_duplicate_in_session(client: tuple) -> None:
    api, connection, session, _ = client
    connection.persist.side_effect = [None, GoogleConnectionError("Keychain unavailable"), None]
    with pytest.raises(GoogleConnectionError):
        api.create_planner_calendar("UTC")
    assert connection.calendar_id == "planner-id"
    api.create_planner_calendar("UTC")
    assert [call.args[0] for call in session.request.call_args_list] == ["POST", "GET"]
