"""Automatic deletion handling retains stable replacements and failure safeguards."""

from unittest.mock import Mock

import pytest

from tests.test_calendar_export import setup, item, remote, NOW
from workload_planner.calendar_export import ExportLedger, preview_export, export_preview, session_event_id, fetch_booked_sessions, unfinished_items
from workload_planner.google_auth import GoogleConnectionError
from workload_planner.scheduling_models import SchedulingTask


def test_replacement_uses_new_stable_id_and_restart_retry_does_not_duplicate(setup):
    api, ledger = setup
    work = item()
    old_id = session_event_id(api.connection,work.session)
    ledger.record(api.connection,work.session,"exported")
    events={old_id:{"id":old_id,"status":"cancelled"}}
    api.get_event.side_effect=events.get
    preview=preview_export(api,(work,),("primary",),ledger,now=NOW)
    def insert(body):
        events[body["id"]]={**body,"status":"confirmed"}
        raise GoogleConnectionError("timeout after creation")
    api.insert_event.side_effect=insert
    assert export_preview(api,preview,("primary",),ledger,now=NOW)[0].status=="uncertain"
    new_id=api.insert_event.call_args.args[0]["id"]
    assert new_id!=old_id
    restored=ExportLedger(ledger.path)
    assert unfinished_items(api.connection,restored)[0].session==work.session
    retry=preview_export(api,(work,),("primary",),restored,now=NOW)
    assert retry.rows[0].status=="already present"
    export_preview(api,retry,("primary",),restored,now=NOW)
    api.insert_event.assert_called_once()
    api.list_planner_events.return_value=[events[new_id]]
    tasks=[SchedulingTask("task",60,NOW.replace(hour=23))]
    assert fetch_booked_sessions(api,tasks,NOW,NOW.replace(hour=23),restored)==(work.session,)


def test_changed_existing_event_is_not_retired_as_deleted(setup):
    api,ledger=setup
    work=item()
    ledger.record(api.connection,work.session,"exported")
    moved=remote(api,work)
    moved["start"]["dateTime"]=NOW.replace(hour=8).isoformat()
    api.get_event.return_value=moved
    p=preview_export(api,(work,),("primary",),ledger,now=NOW)
    assert p.rows[0].status=="changed; review required"
    assert ledger.read()[moved["id"]]["status"]=="exported"
    api.insert_event.assert_not_called()


def test_generation_rechecks_all_missing_events_before_retiring_any_records(setup):
    api,ledger=setup
    first,second=item(9),item(11)
    for work in (first,second):
        ledger.record(api.connection,work.session,"exported")
    api.list_planner_events.return_value=[]
    api.get_event.side_effect=[None,None,None,remote(api,second)]
    with pytest.raises(GoogleConnectionError,match="changed|present|again"):
        fetch_booked_sessions(api,[SchedulingTask("task",120,NOW.replace(hour=23))],NOW,NOW.replace(hour=23),ledger)
    assert all(r["status"]=="exported" for r in ledger.read().values())


def test_failed_remote_check_keeps_ledger_untouched(setup):
    api,ledger=setup
    work=item()
    ledger.record(api.connection,work.session,"exported")
    api.list_planner_events.return_value=[]
    api.get_event.side_effect=GoogleConnectionError("access denied")
    with pytest.raises(GoogleConnectionError):
        fetch_booked_sessions(api,[SchedulingTask("task",60,NOW.replace(hour=23))],NOW,NOW.replace(hour=23),ledger)
    assert next(iter(ledger.read().values()))["status"]=="exported"


def test_pending_missing_receipts_still_require_uncertain_export_recovery(setup):
    api,ledger=setup
    ledger.record(api.connection,item().session,"pending")
    api.list_planner_events.return_value=[]
    with pytest.raises(GoogleConnectionError,match="unfinished"):
        fetch_booked_sessions(api,[SchedulingTask("task",60,NOW.replace(hour=23))],NOW,NOW.replace(hour=23),ledger)
    assert next(iter(ledger.read().values()))["status"]=="pending"


def test_repeated_deleted_replacements_retire_each_old_id(setup):
    api,ledger=setup
    work=item()
    events={}
    api.get_event.side_effect=events.get
    api.insert_event.side_effect=lambda body: events.setdefault(body["id"],{**body,"status":"confirmed"})
    ids=[]
    for _ in range(3):
        p=preview_export(api,(work,),("primary",),ledger,now=NOW)
        assert export_preview(api,p,("primary",),ledger,now=NOW)[0].status=="exported"
        key=api.insert_event.call_args.args[0]["id"]
        ids.append(key)
        events[key]["status"]="cancelled"
        assert preview_export(api,(work,),("primary",),ledger,now=NOW).rows[0].status=="ready"
    assert len(set(ids))==3
    assert len(ledger.read())==3
    assert all(r["status"]=="deleted" for r in ledger.read().values())


def test_old_export_approval_cannot_send_a_replacement_without_new_preview(setup):
    api,ledger=setup
    work=item()
    old_preview=preview_export(api,(work,),("primary",),ledger,now=NOW)
    ledger.record(api.connection,work.session,"exported")
    preview_export(api,(work,),("primary",),ledger,now=NOW)
    with pytest.raises(GoogleConnectionError,match="history changed"):
        export_preview(api,old_preview,("primary",),ledger,now=NOW)
    api.insert_event.assert_not_called()


def test_local_save_failure_preserves_receipts_and_sends_no_events(setup,monkeypatch):
    api,ledger=setup
    work=item()
    ledger.record(api.connection,work.session,"exported")
    original=ledger.path.read_bytes()
    monkeypatch.setattr(ledger,"_write",Mock(side_effect=GoogleConnectionError("disk unavailable")))
    with pytest.raises(GoogleConnectionError):
        preview_export(api,(work,),("primary",),ledger,now=NOW)
    assert ledger.path.read_bytes()==original
    api.insert_event.assert_not_called()


def test_generation_ignores_receipts_for_other_accounts(setup):
    api,ledger=setup
    work=item()
    ledger.record(api.connection,work.session,"exported")
    api.connection.subject="other-user"
    api.list_planner_events.return_value=[]
    assert fetch_booked_sessions(api,[SchedulingTask("task",60,NOW.replace(hour=23))],NOW,NOW.replace(hour=23),ledger)==()
    api.get_event.assert_not_called()
