"""Deleted confirmed exports become ready again after successful availability checks."""
from unittest.mock import Mock

import pytest

from tests.test_calendar_export import setup, item, remote, NOW
from workload_planner.calendar_export import ExportLedger, preview_export, export_preview, session_event_id, fetch_booked_sessions
from workload_planner.calendar_planning import BusyPeriod
from workload_planner.google_auth import GoogleConnectionError
from workload_planner.scheduling_models import SchedulingTask


@pytest.mark.parametrize("cancelled", [False,True])
def test_preview_detects_deletion_and_approved_export_recreates_only_missing_event(setup,cancelled):
    api,ledger=setup
    work=item()
    old_id=session_event_id(api.connection,work.session)
    ledger.record(api.connection,work.session,"exported")
    events={old_id:{"id":old_id,"status":"cancelled"}} if cancelled else {}
    api.get_event.side_effect=events.get
    preview=preview_export(api,(work,),("primary",),ledger,now=NOW)
    assert preview.rows[0].status=="ready"
    assert "replacement" in preview.rows[0].message.lower()
    assert preview.event_ids[0]!=old_id
    api.insert_event.assert_not_called()
    assert ledger.read()[old_id]["status"]=="deleted"
    api.insert_event.side_effect=lambda body: events.setdefault(body["id"],{**body,"status":"confirmed"})
    result=export_preview(api,preview,("primary",),ledger,now=NOW)
    assert result[0].status=="exported"
    retry=preview_export(api,(work,),("primary",),ExportLedger(ledger.path),now=NOW)
    assert retry.rows[0].status=="already present"
    export_preview(api,retry,("primary",),ledger,now=NOW)
    api.insert_event.assert_called_once()


def test_conflict_still_blocks_reexport_even_when_previous_event_was_deleted(setup):
    api,ledger=setup
    work=item()
    ledger.record(api.connection,work.session,"exported")
    api.busy_periods.return_value=(BusyPeriod(work.session.start_at,work.session.end_at),)
    preview=preview_export(api,(work,),("primary",),ledger,now=NOW)
    assert preview.rows[0].status=="conflict"
    assert next(iter(ledger.read().values()))["status"]=="exported"
    api.insert_event.assert_not_called()


@pytest.mark.parametrize("failing",["get_event","busy_periods"])
def test_failed_read_is_not_treated_as_permission_to_recreate(setup,failing):
    api,ledger=setup
    work=item()
    ledger.record(api.connection,work.session,"exported")
    getattr(api,failing).side_effect=GoogleConnectionError("access denied")
    with pytest.raises(GoogleConnectionError):
        preview_export(api,(work,),("primary",),ledger,now=NOW)
    assert next(iter(ledger.read().values()))["status"]=="exported"
    api.insert_event.assert_not_called()


def test_mixed_present_and_deleted_exports_do_not_duplicate_present_session(setup):
    api,ledger=setup
    first,second=item(9),item(11)
    for work in (first,second):
        ledger.record(api.connection,work.session,"exported")
    events={session_event_id(api.connection,first.session):remote(api,first)}
    api.get_event.side_effect=events.get
    preview=preview_export(api,(first,second),("primary",),ledger,now=NOW)
    assert [r.status for r in preview.rows]==["already present","ready"]
    api.insert_event.side_effect=lambda body: events.setdefault(body["id"],{**body,"status":"confirmed"})
    export_preview(api,preview,("primary",),ledger,now=NOW)
    api.insert_event.assert_called_once()
    assert api.insert_event.call_args.args[0]["start"]["dateTime"]==second.session.start_at.isoformat()


def test_generation_automatically_releases_missing_confirmed_exports(setup):
    api,ledger=setup
    work=item()
    ledger.record(api.connection,work.session,"exported")
    api.list_planner_events.return_value=[]
    tasks=[SchedulingTask("task",60,NOW.replace(hour=23))]
    assert fetch_booked_sessions(api,tasks,NOW,NOW.replace(hour=23),ledger)==()
    assert next(iter(ledger.read().values()))["status"]=="deleted"
    api.insert_event.assert_not_called()


def test_reappeared_event_is_not_retired_during_preview(setup):
    api,ledger=setup
    work=item()
    ledger.record(api.connection,work.session,"exported")
    api.get_event.side_effect=[None,remote(api,work)]
    with pytest.raises(GoogleConnectionError,match="changed|present|preview"):
        preview_export(api,(work,),("primary",),ledger,now=NOW)
    assert next(iter(ledger.read().values()))["status"]=="exported"
    api.insert_event.assert_not_called()


def test_mixed_free_and_busy_deleted_sessions_keep_accurate_statuses(setup):
    api,ledger=setup
    first,second=item(9),item(11)
    for work in (first,second):
        ledger.record(api.connection,work.session,"exported")
    api.busy_periods.return_value=(BusyPeriod(second.session.start_at,second.session.end_at),)
    p=preview_export(api,(first,second),("primary",),ledger,now=NOW)
    assert [r.status for r in p.rows]==["ready","conflict"]
    assert ledger.read()[session_event_id(api.connection,second.session)]["status"]=="exported"
