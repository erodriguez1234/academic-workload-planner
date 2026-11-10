"""Reviewed export is idempotent, conflict-aware, and isolated to owned events."""

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import Mock

import pytest

from workload_planner.calendar_export import (
    ExportItem, ExportLedger, export_preview, preview_export, session_event_id,
    fetch_booked_sessions, unfinished_items,
)
from workload_planner.calendar_planning import BusyPeriod
from workload_planner.google_auth import GoogleConnectionError
from workload_planner.scheduling_models import SchedulingTask, StudySession

UTC = timezone.utc
NOW = datetime(2099, 1, 1, tzinfo=UTC)


def item(hour: int = 9, assignment_id: str = "task") -> ExportItem:
    return ExportItem(StudySession(assignment_id, NOW.replace(hour=hour), NOW.replace(hour=hour + 1)), "Synthetic assignment", "Synthetic course")


@pytest.fixture
def setup(tmp_path: Path) -> tuple:
    connection = Mock(subject="user", client_id="client", calendar_id="planner", marker="owner")
    api = Mock(connection=connection)
    api.check_planner_calendar.return_value = {"id": "planner", "description": "Academic Workload Planner / owner"}
    api.get_event.return_value = None
    api.busy_periods.return_value = ()
    return api, ExportLedger(tmp_path / "exports.json")


def remote(api: Mock, work: ExportItem) -> dict:
    event_id = session_event_id(api.connection, work.session)
    return {"id": event_id, "status": "confirmed", "start": {"dateTime": work.session.start_at.isoformat()}, "end": {"dateTime": work.session.end_at.isoformat()},
            "extendedProperties": {"private": {"awp_owner": "owner", "awp_assignment": work.session.assignment_id, "awp_session": event_id}}}


def test_preview_is_read_only_then_export_inserts_only_approved_sessions(setup: tuple) -> None:
    api, ledger = setup
    work = item()
    preview = preview_export(api, (work,), ("primary",), ledger, now=NOW)
    api.insert_event.assert_not_called()
    assert preview.rows[0].status == "ready"
    api.insert_event.return_value = remote(api, work)
    result = export_preview(api, preview, ("primary",), ledger, now=NOW)
    assert result[0].status == "exported"
    body = api.insert_event.call_args.args[0]
    assert body["id"] == session_event_id(api.connection, work.session)
    assert body["transparency"] == "opaque" and "attendees" not in body
    assert body["extendedProperties"]["private"]["awp_owner"] == "owner"
    assert ledger.path.stat().st_mode & 0o777 == 0o600


def test_restart_retry_recognizes_existing_event_without_creating_duplicate(setup: tuple) -> None:
    api, ledger = setup
    work = item()
    preview = preview_export(api, (work,), ("primary",), ledger, now=NOW)
    api.insert_event.side_effect = GoogleConnectionError("timeout")
    assert export_preview(api, preview, ("primary",), ledger, now=NOW)[0].status == "uncertain"
    api.get_event.return_value = remote(api, work)
    restored = ExportLedger(ledger.path)
    retry = preview_export(api, (work,), ("primary",), restored, now=NOW)
    assert retry.rows[0].status == "already present"
    export_preview(api, retry, ("primary",), restored, now=NOW)
    assert api.insert_event.call_count == 1


def test_fresh_calendar_conflict_blocks_export_after_preview(setup: tuple) -> None:
    api, ledger = setup
    work = item()
    preview = preview_export(api, (work,), ("primary",), ledger, now=NOW)
    api.busy_periods.return_value = (BusyPeriod(work.session.start_at, work.session.end_at),)
    assert export_preview(api, preview, ("primary",), ledger, now=NOW)[0].status == "conflict"
    api.insert_event.assert_not_called()


def test_failed_busy_read_never_writes(setup: tuple) -> None:
    api, ledger = setup
    api.busy_periods.side_effect = GoogleConnectionError("busy read denied")
    with pytest.raises(GoogleConnectionError):
        preview_export(api, (item(),), ("primary",), ledger, now=NOW)
    api.insert_event.assert_not_called()


def test_changed_account_or_selected_calendars_invalidates_approval(setup: tuple) -> None:
    api, ledger = setup
    preview = preview_export(api, (item(),), ("primary",), ledger, now=NOW)
    with pytest.raises(GoogleConnectionError, match="preview"):
        export_preview(api, preview, ("primary", "other"), ledger, now=NOW)
    api.connection.subject = "different-user"
    with pytest.raises(GoogleConnectionError, match="preview"):
        export_preview(api, preview, ("primary",), ledger, now=NOW)
    api.insert_event.assert_not_called()


def test_unrelated_or_manually_moved_event_is_not_overwritten(setup: tuple) -> None:
    api, ledger = setup
    work = item()
    event = remote(api, work)
    event["start"]["dateTime"] = NOW.replace(hour=8).isoformat()
    api.get_event.return_value = event
    preview = preview_export(api, (work,), ("primary",), ledger, now=NOW)
    assert preview.rows[0].status == "changed; review required"
    api.insert_event.assert_not_called()


def test_partial_failure_reports_all_approved_work_and_stops_writes(setup: tuple) -> None:
    api, ledger = setup
    work = (item(9), item(11), item(13))
    preview = preview_export(api, work, ("primary",), ledger, now=NOW)
    api.insert_event.side_effect = [remote(api, work[0]), GoogleConnectionError("timeout")]
    result = export_preview(api, preview, ("primary",), ledger, now=NOW)
    assert [row.status for row in result] == ["exported", "uncertain", "not attempted"]
    assert sum(row.item.session.duration_minutes for row in result) == 180
    assert api.insert_event.call_count == 2
    assert len(unfinished_items(api.connection, ExportLedger(ledger.path))) == 1


def test_ledger_failure_stops_remote_insert(setup: tuple, monkeypatch: pytest.MonkeyPatch) -> None:
    api, ledger = setup
    preview = preview_export(api, (item(),), ("primary",), ledger, now=NOW)
    monkeypatch.setattr(ledger, "record", Mock(side_effect=GoogleConnectionError("disk unavailable")))
    result = export_preview(api, preview, ("primary",), ledger, now=NOW)
    assert result[0].status == "failed"
    api.insert_event.assert_not_called()


def test_preexisting_booked_work_is_retained_but_modified_work_blocks_replanning(setup: tuple) -> None:
    api, ledger = setup
    work = item()
    api.list_planner_events.return_value = [remote(api, work)]
    tasks = [SchedulingTask("task", 120, NOW.replace(hour=20))]
    booked = fetch_booked_sessions(api, tasks, NOW, NOW.replace(hour=23), ledger)
    assert booked == (work.session,)
    api.list_planner_events.return_value[0]["end"]["dateTime"] = NOW.replace(hour=12).isoformat()
    with pytest.raises(GoogleConnectionError, match="changed"):
        fetch_booked_sessions(api, tasks, NOW, NOW.replace(hour=23), ledger)


def test_unowned_calendar_and_past_sessions_cannot_be_exported(setup: tuple) -> None:
    api, ledger = setup
    preview = preview_export(api, (item(),), ("primary",), ledger, now=NOW.replace(hour=10))
    assert preview.rows[0].status == "already started"
    api.check_planner_calendar.return_value["description"] = "Unrelated"
    with pytest.raises(GoogleConnectionError, match="ownership"):
        preview_export(api, (item(),), ("primary",), ledger, now=NOW)
    api.insert_event.assert_not_called()


def test_409_race_accepts_only_the_matching_existing_event(setup: tuple) -> None:
    api, ledger = setup
    work = item()
    preview = preview_export(api, (work,), ("primary",), ledger, now=NOW)
    api.get_event.side_effect = [None, remote(api, work)]
    api.insert_event.side_effect = GoogleConnectionError("already exists", status_code=409)
    assert export_preview(api, preview, ("primary",), ledger, now=NOW)[0].status == "already present"
    assert not unfinished_items(api.connection, ledger)


def test_confirmed_retry_resolves_uncertain_local_receipt(setup: tuple) -> None:
    api, ledger = setup
    work = item()
    ledger.record(api.connection, work.session, "uncertain")
    api.get_event.return_value = remote(api, work)
    assert preview_export(api, (work,), ("primary",), ledger, now=NOW).rows[0].status == "already present"
    assert not unfinished_items(api.connection, ledger)


def test_malformed_event_metadata_blocks_export_instead_of_crashing(setup: tuple) -> None:
    api, ledger = setup
    api.get_event.return_value = {"extendedProperties": {"private": "invalid"}}
    preview = preview_export(api, (item(),), ("primary",), ledger, now=NOW)
    assert preview.rows[0].status == "changed; review required"
    api.insert_event.assert_not_called()
