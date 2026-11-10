"""Reviewed, append-only export with stable event IDs and a private intent ledger."""

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from tempfile import NamedTemporaryFile
from threading import Lock, RLock
from uuid import NAMESPACE_URL, uuid5

from workload_planner.calendar_planning import BusyPeriod
from workload_planner.google_auth import GoogleConnection, GoogleConnectionError
from workload_planner.google_calendar import GoogleCalendarClient
from workload_planner.scheduling_models import SchedulingTask, StudySession

UTC = timezone.utc
DEFAULT_LEDGER_PATH = Path(__file__).resolve().parents[1] / ".local" / "calendar_exports.json"
_STORE_LOCK = RLock()
_EXPORT_LOCK = Lock()


def utc_now() -> datetime:
    return datetime.now(UTC)


def connection_binding(connection: GoogleConnection) -> str:
    values = (connection.client_id, connection.subject, connection.calendar_id, connection.marker)
    if not all(isinstance(value, str) and value for value in values) or connection.calendar_id == "primary":
        raise GoogleConnectionError("Connect a verified Google account and select its dedicated planner calendar first.")
    return sha256(json.dumps(values).encode()).hexdigest()


def session_event_id(connection: GoogleConnection, session: StudySession) -> str:
    identity = (connection_binding(connection), session.assignment_id,
                session.start_at.astimezone(UTC).isoformat(), session.end_at.astimezone(UTC).isoformat())
    return "a" + uuid5(NAMESPACE_URL, json.dumps(identity)).hex


@dataclass(frozen=True)
class ExportItem:
    session: StudySession
    title: str
    course: str


@dataclass(frozen=True)
class ExportRow:
    item: ExportItem
    status: str
    message: str = ""


@dataclass(frozen=True)
class ExportPreview:
    binding: str
    calendar_ids: tuple[str, ...]
    rows: tuple[ExportRow, ...]
    checked_at: datetime


class ExportLedger:
    """Persist IDs, times, and intent states only; no tokens or event titles."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = DEFAULT_LEDGER_PATH if path is None else path

    def read(self) -> dict[str, dict]:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                raise ValueError("invalid ledger")
            for event_id, record in data.items():
                if not isinstance(record, dict) or record.get("status") not in ("pending", "exported", "uncertain", "failed"):
                    raise ValueError("invalid ledger")
                if not all(isinstance(record.get(key), str) and record[key] for key in ("binding", "assignment_id", "start", "end")):
                    raise ValueError("invalid ledger")
                StudySession(record["assignment_id"], datetime.fromisoformat(record["start"]), datetime.fromisoformat(record["end"]))
            return data
        except FileNotFoundError:
            return {}
        except (OSError, ValueError, TypeError):
            raise GoogleConnectionError("The local export ledger could not be read. Resolve it before exporting; it was not overwritten.") from None

    def record(self, connection: GoogleConnection, session: StudySession, status: str) -> None:
        with _STORE_LOCK:
            data = self.read()
            data[session_event_id(connection, session)] = {
                "binding": connection_binding(connection), "assignment_id": session.assignment_id,
                "start": session.start_at.astimezone(UTC).isoformat(), "end": session.end_at.astimezone(UTC).isoformat(), "status": status,
            }
            temporary = None
            try:
                self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
                with NamedTemporaryFile(mode="w", encoding="utf-8", dir=self.path.parent, delete=False) as file:
                    temporary = Path(file.name)
                    os.fchmod(file.fileno(), 0o600)
                    json.dump(data, file, indent=2)
                    file.flush()
                    os.fsync(file.fileno())
                os.replace(temporary, self.path)
            except OSError:
                raise GoogleConnectionError("Export intent could not be saved locally. No further events will be sent.") from None
            finally:
                if temporary is not None:
                    temporary.unlink(missing_ok=True)


def _event_session(event: dict) -> StudySession:
    try:
        assignment_id = event["extendedProperties"]["private"]["awp_assignment"]
        return StudySession(assignment_id, datetime.fromisoformat(event["start"]["dateTime"]), datetime.fromisoformat(event["end"]["dateTime"]))
    except (KeyError, TypeError, ValueError):
        raise GoogleConnectionError("A planner event was changed into an unsupported interval; review it before replanning.") from None


def _matches(connection: GoogleConnection, event: dict, session: StudySession) -> bool:
    properties = event.get("extendedProperties") or {}
    private = (properties.get("private") or {}) if isinstance(properties, dict) else {}
    if not isinstance(private, dict):
        return False
    event_id = session_event_id(connection, session)
    try:
        return (event.get("status") != "cancelled" and event.get("id") == event_id
                and private.get("awp_owner") == connection.marker and private.get("awp_session") == event_id
                and _event_session(event) == session)
    except GoogleConnectionError:
        return False


def _target(client: GoogleCalendarClient) -> None:
    connection_binding(client.connection)
    metadata = client.check_planner_calendar()
    if metadata.get("description") != f"Academic Workload Planner / {client.connection.marker}":
        raise GoogleConnectionError("The target calendar's ownership marker does not match. Export is blocked.")


def unfinished_items(connection: GoogleConnection, ledger: ExportLedger) -> tuple[ExportItem, ...]:
    binding = connection_binding(connection)
    items = []
    for event_id, record in ledger.read().items():
        if record["binding"] == binding and record["status"] in ("pending", "uncertain"):
            session = StudySession(record["assignment_id"], datetime.fromisoformat(record["start"]), datetime.fromisoformat(record["end"]))
            if session_event_id(connection, session) != event_id:
                raise GoogleConnectionError("An unfinished export record is invalid; review the local ledger.")
            items.append(ExportItem(session, "Previously approved study session", ""))
    return tuple(items)


def fetch_booked_sessions(
    client: GoogleCalendarClient, tasks: list[SchedulingTask], start: datetime, end: datetime, ledger: ExportLedger,
) -> tuple[StudySession, ...]:
    """Retain verified future bookings, including later sessions before task deadlines."""
    _target(client)
    binding = connection_binding(client.connection)
    end = max([end, *(t.due_at for t in tasks if t.due_at is not None)])
    records = ledger.read()
    selected = {task.assignment_id for task in tasks}
    booked, seen = [], set()
    for event in client.list_planner_events(start, end):
        properties = event.get("extendedProperties") or {}
        if not isinstance(properties, dict) or not isinstance(properties.get("private", {}), dict):
            raise GoogleConnectionError("Google returned invalid planner-event metadata; review it before planning.")
        private = properties.get("private", {})
        if private.get("awp_owner") != client.connection.marker or event.get("status") == "cancelled":
            continue
        session = _event_session(event)
        event_id = event.get("id")
        if not _matches(client.connection, event, session):
            if session.assignment_id in selected:
                raise GoogleConnectionError("A previously booked planner session changed. Review it before generating a new schedule.")
            continue
        if event_id in seen:
            raise GoogleConnectionError("Google returned duplicate planner events; planning stopped.")
        seen.add(event_id)
        booked.append(session)
        if records.get(event_id, {}).get("status") in ("pending", "uncertain"):
            ledger.record(client.connection, session, "exported")
    for event_id, record in records.items():
        if record["binding"] != binding or record["assignment_id"] not in selected or record["status"] == "failed" or event_id in seen:
            continue
        session = StudySession(record["assignment_id"], datetime.fromisoformat(record["start"]), datetime.fromisoformat(record["end"]))
        if session.end_at <= start or session.start_at >= end:
            continue
        event = client.get_event(event_id)
        if event and _matches(client.connection, event, session):
            booked.append(session)
            ledger.record(client.connection, session, "exported")
        elif record["status"] in ("pending", "uncertain"):
            raise GoogleConnectionError("A previous export is unfinished. Use Review unfinished exports before generating another plan for this assignment.")
        else:
            raise GoogleConnectionError("A previously exported session was deleted or changed. Automatic reconciliation is not enabled; review it first.")
    return tuple(booked)


def _overlaps(session: StudySession, busy: BusyPeriod) -> bool:
    return session.start_at.astimezone(UTC) < busy.end_at.astimezone(UTC) and busy.start_at.astimezone(UTC) < session.end_at.astimezone(UTC)


def preview_export(
    client: GoogleCalendarClient, items: tuple[ExportItem, ...], calendar_ids: tuple[str, ...], ledger: ExportLedger,
    *, now: datetime | None = None,
) -> ExportPreview:
    _target(client)
    now = utc_now() if now is None else now
    ids = tuple(sorted(set(calendar_ids)))
    if not ids or not items:
        raise GoogleConnectionError("Select sessions and conflict-check calendars before previewing.")
    sessions = sorted((work.session for work in items), key=lambda s: s.start_at.astimezone(UTC))
    if any(b.start_at.astimezone(UTC) < a.end_at.astimezone(UTC) for a, b in zip(sessions, sessions[1:])):
        raise GoogleConnectionError("Approved sessions overlap; generate a fresh schedule.")
    records = ledger.read()
    binding = connection_binding(client.connection)
    event_ids = {session_event_id(client.connection, work.session) for work in items}
    rows = []
    for work in items:
        event_id = session_event_id(client.connection, work.session)
        existing = client.get_event(event_id)
        if existing is not None:
            status = "already present" if _matches(client.connection, existing, work.session) else "changed; review required"
            if status == "already present" and records.get(event_id, {}).get("status") in ("pending", "uncertain"):
                ledger.record(client.connection, work.session, "exported")
        elif records.get(event_id, {}).get("status") == "exported":
            status = "changed; review required"
        elif work.session.start_at.astimezone(UTC) <= now.astimezone(UTC):
            status = "already started"
        elif any(r["binding"] == binding and r["assignment_id"] == work.session.assignment_id and r["status"] in ("pending", "uncertain") and datetime.fromisoformat(r["end"]) > now and key not in event_ids for key, r in records.items()):
            status = "unfinished export; recover first"
        else:
            status = "ready"
        rows.append(ExportRow(work, status))
    ready = [row.item.session for row in rows if row.status == "ready"]
    if ready:
        busy = client.busy_periods(list(ids), min(s.start_at for s in ready), max(s.end_at for s in ready))
        rows = [ExportRow(row.item, "conflict") if row.status == "ready" and any(_overlaps(row.item.session, b) for b in busy) else row for row in rows]
    return ExportPreview(binding, ids, tuple(rows), now)


def _event_body(connection: GoogleConnection, work: ExportItem) -> dict:
    event_id = session_event_id(connection, work.session)
    return {
        "id": event_id, "summary": f"Study: {work.title}",
        "description": f"Course: {work.course}\n{work.session.duration_minutes} active working minutes. Created by Academic Workload Planner.",
        "start": {"dateTime": work.session.start_at.astimezone(UTC).isoformat()},
        "end": {"dateTime": work.session.end_at.astimezone(UTC).isoformat()},
        "transparency": "opaque", "reminders": {"useDefault": False},
        "extendedProperties": {"private": {"awp_owner": connection.marker, "awp_assignment": work.session.assignment_id, "awp_session": event_id}},
    }


def export_preview(
    client: GoogleCalendarClient, preview: ExportPreview, calendar_ids: tuple[str, ...], ledger: ExportLedger,
    *, now: datetime | None = None,
) -> tuple[ExportRow, ...]:
    """Recheck approval/context/conflicts; write stable IDs only after local intent."""
    if preview.binding != connection_binding(client.connection) or preview.calendar_ids != tuple(sorted(set(calendar_ids))):
        raise GoogleConnectionError("Google account or calendars changed; create and review a fresh preview.")
    if not _EXPORT_LOCK.acquire(blocking=False):
        raise GoogleConnectionError("Another export is in progress. Check its results before retrying.")
    try:
        fresh = preview_export(client, tuple(row.item for row in preview.rows), calendar_ids, ledger, now=now)
        results, stopped = [], False
        for original, row in zip(preview.rows, fresh.rows):
            if original.status != "ready" or row.status != "ready":
                if original.status == "already present" and row.status == "ready":
                    results.append(ExportRow(row.item, "changed; review required"))
                else:
                    results.append(row if original.status in ("ready", "already present") else original)
                continue
            if stopped:
                results.append(ExportRow(row.item, "not attempted"))
                continue
            session = row.item.session
            # Check again directly before this write; Google has no atomic
            # free/busy-and-insert transaction, so an external race remains possible.
            try:
                if any(_overlaps(session, busy) for busy in client.busy_periods(list(calendar_ids), session.start_at, session.end_at)):
                    results.append(ExportRow(row.item, "conflict"))
                    continue
                ledger.record(client.connection, session, "pending")
            except GoogleConnectionError as error:
                results.append(ExportRow(row.item, "failed", str(error)))
                stopped = True
                continue
            try:
                event = client.insert_event(_event_body(client.connection, row.item))
                if not _matches(client.connection, event, session):
                    raise GoogleConnectionError("Google's event response could not be verified.")
            except GoogleConnectionError as error:
                if error.status_code == 409:
                    try:
                        event = client.get_event(session_event_id(client.connection, session))
                    except GoogleConnectionError:
                        event = None
                    if event and _matches(client.connection, event, session):
                        try:
                            ledger.record(client.connection, session, "exported")
                            results.append(ExportRow(row.item, "already present"))
                        except GoogleConnectionError as save_error:
                            results.append(ExportRow(row.item, "exported; receipt save failed", str(save_error)))
                            stopped = True
                        continue
                status = "failed" if error.status_code in (400, 401, 403, 404, 409, 429) else "uncertain"
                try:
                    ledger.record(client.connection, session, status)
                except GoogleConnectionError:
                    pass  # The durable pending record already protects this ID.
                results.append(ExportRow(row.item, status, str(error)))
                stopped = True
                continue
            try:
                ledger.record(client.connection, session, "exported")
                results.append(ExportRow(row.item, "exported"))
            except GoogleConnectionError:
                results.append(ExportRow(row.item, "exported; receipt save failed"))
                stopped = True
        return tuple(results)
    finally:
        _EXPORT_LOCK.release()
