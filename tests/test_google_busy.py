"""Calendar selection/free-busy/event transport with synthetic responses."""

from datetime import datetime, timezone
from unittest.mock import Mock

import pytest

from workload_planner.google_auth import GoogleConnectionError
from workload_planner.google_calendar import GoogleCalendarClient

START = datetime(2026, 11, 9, tzinfo=timezone.utc)
END = datetime(2026, 11, 10, tzinfo=timezone.utc)


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> tuple:
    connection = Mock(calendar_id="planner-id")
    session = Mock()
    session.__enter__ = Mock(return_value=session)
    session.__exit__ = Mock(return_value=False)
    monkeypatch.setattr("workload_planner.google_calendar.AuthorizedSession", Mock(return_value=session))
    return GoogleCalendarClient(connection), session


def response(data: dict, status: int = 200) -> Mock:
    result = Mock(status_code=status)
    result.json.return_value = data
    return result


def test_calendar_list_follows_every_page(client: tuple) -> None:
    api, http = client
    http.request.side_effect = [response({"items": [{"id": "first", "summary": "Work"}], "nextPageToken": "next"}), response({"items": [{"id": "second"}]})]
    assert [item["id"] for item in api.list_calendars()] == ["first", "second"]
    assert http.request.call_args.kwargs["params"]["pageToken"] == "next"


def test_freebusy_gets_only_intervals_and_includes_dedicated_calendar(client: tuple) -> None:
    api, http = client
    http.request.return_value = response({"calendars": {
        "primary": {"busy": [{"start": "2026-11-09T09:00:00Z", "end": "2026-11-09T10:00:00Z"}]},
        "planner-id": {"busy": []},
    }})
    busy = api.busy_periods(["primary"], START, END)
    assert len(busy) == 1 and busy[0].start_at.hour == 9
    assert {item["id"] for item in http.request.call_args.kwargs["json"]["items"]} == {"primary", "planner-id"}


@pytest.mark.parametrize("entry", [None, {"errors": [{"reason": "notFound"}]}, {"busy": [{"start": "bad", "end": "bad"}]}])
def test_incomplete_busy_read_blocks_planning(client: tuple, entry: object) -> None:
    api, http = client
    http.request.return_value = response({"calendars": {"primary": entry, "planner-id": {"busy": []}}})
    with pytest.raises(GoogleConnectionError, match="busy"):
        api.busy_periods(["primary"], START, END)


def test_planner_events_are_expanded_and_paginated(client: tuple) -> None:
    api, http = client
    http.request.side_effect = [response({"items": [{"id": "one"}], "nextPageToken": "next"}), response({"items": [{"id": "two"}]})]
    assert len(api.list_planner_events(START, END)) == 2
    assert http.request.call_args.kwargs["params"]["singleEvents"] == "true"


def test_missing_event_and_deleted_event_are_distinguished(client: tuple) -> None:
    api, http = client
    http.request.return_value = response({}, 404)
    assert api.get_event("event-id") is None
    http.request.return_value = response({}, 410)
    assert api.get_event("event-id")["status"] == "cancelled"


def test_event_writes_only_target_dedicated_calendar_and_disable_notifications(client: tuple) -> None:
    api, http = client
    http.request.return_value = response({"id": "fixed-event-id"})
    api.insert_event({"id": "fixed-event-id"})
    call = http.request.call_args
    assert call.args[0] == "POST" and "/planner-id/events" in call.args[1]
    assert call.kwargs["params"]["sendUpdates"] == "none"
