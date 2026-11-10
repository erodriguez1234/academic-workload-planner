"""Calendar metadata, busy intervals, and writes restricted to the planner calendar."""

from datetime import datetime, timezone
from urllib.parse import quote
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from google.auth.transport.requests import AuthorizedSession

from workload_planner.google_auth import GoogleConnection, GoogleConnectionError
from workload_planner.calendar_planning import BusyPeriod

API_URL = "https://www.googleapis.com/calendar/v3/calendars"
CALENDAR_NAME = "Academic Workload Planner"


class GoogleCalendarClient:
    def __init__(self, connection: GoogleConnection) -> None:
        self.connection = connection

    def _request(self, method: str, calendar_id: str | None = None, body: dict | None = None) -> dict:
        path = "/calendars" if calendar_id is None else f"/calendars/{quote(calendar_id, safe='')}"
        result = self._call(method, path, body=body)
        if not isinstance(result.get("id"), str) or not result["id"] or result["id"] == "primary":
            raise GoogleConnectionError("Google returned invalid planner calendar metadata.")
        return result

    def _call(self, method: str, path: str, *, body: dict | None = None, params: dict | None = None) -> dict:
        self.connection.ensure_fresh()
        url = "https://www.googleapis.com/calendar/v3" + path
        try:
            with AuthorizedSession(self.connection.credentials, max_refresh_attempts=0) as session:
                response = session.request(method, url, json=body, params=params, timeout=20)
            if response.status_code not in (200, 201):
                hints = {
                    401: "authorization expired; reconnect or authorize again",
                    403: "permission denied; check Calendar consent and school account policy",
                    404: "calendar not found or no longer accessible",
                    429: "rate limited; wait before checking again",
                }
                raise GoogleConnectionError(f"Google Calendar HTTP {response.status_code}: {hints.get(response.status_code, 'request failed; check again later')}.", status_code=response.status_code)
            result = response.json()
            if not isinstance(result, dict):
                raise GoogleConnectionError("Google returned an invalid response.")
            return result
        except GoogleConnectionError:
            raise
        except Exception:
            raise GoogleConnectionError("Google Calendar connection failed or timed out. No automatic write retry was made.") from None

    def check_planner_calendar(self) -> dict:
        if not self.connection.calendar_id or self.connection.calendar_id == "primary":
            raise GoogleConnectionError("No dedicated planner calendar is selected.")
        result = self._request("GET", self.connection.calendar_id)
        if result["id"] != self.connection.calendar_id:
            raise GoogleConnectionError("Google returned a different calendar than requested.")
        return result

    def create_planner_calendar(self, timezone_name: str) -> dict:
        """Create once on explicit action; uncertain results require recovery."""
        if self.connection.calendar_id:
            return self.check_planner_calendar()
        if self.connection.creation_pending:
            raise GoogleConnectionError("A prior calendar creation may have succeeded. Check Google Calendar and recover its ID before trying another creation.")
        try:
            ZoneInfo(timezone_name)
        except (ZoneInfoNotFoundError, ValueError):
            raise GoogleConnectionError("Enter a valid student timezone before creating the calendar.") from None
        self.connection.ensure_fresh()
        self.connection.creation_pending = True
        self.connection.persist()
        try:
            result = self._request("POST", body={
                "summary": CALENDAR_NAME, "timeZone": timezone_name,
                "description": f"Academic Workload Planner / {self.connection.marker}",
            })
        except GoogleConnectionError as error:
            if error.status_code in (400, 401, 403, 404, 429):
                self.connection.creation_pending = False
                self.connection.persist()
            raise
        self.connection.calendar_id = result["id"]
        self.connection.creation_pending = False
        self.connection.persist()
        return result

    def recover_calendar(self, calendar_id: str) -> dict:
        """Select only a calendar carrying this connection's saved ownership marker."""
        if not calendar_id.strip() or calendar_id == "primary":
            raise GoogleConnectionError("Enter the dedicated calendar ID, not primary.")
        result = self._request("GET", calendar_id.strip())
        if result.get("description") != f"Academic Workload Planner / {self.connection.marker}" or result["id"] != calendar_id.strip():
            raise GoogleConnectionError("Calendar ownership marker does not match this planner connection.")
        self.connection.calendar_id = result["id"]
        self.connection.creation_pending = False
        self.connection.persist()
        return result

    def _pages(self, path: str, params: dict) -> list[dict]:
        records, seen = [], set()
        params = params.copy()
        while True:
            page = self._call("GET", path, params=params)
            items = page.get("items", [])
            if not isinstance(items, list) or not all(isinstance(item, dict) for item in items):
                raise GoogleConnectionError("Google returned an invalid calendar page; results are incomplete.")
            records.extend(items)
            token = page.get("nextPageToken")
            if not token:
                return records
            if not isinstance(token, str) or token in seen:
                raise GoogleConnectionError("Google pagination repeated; results are incomplete.")
            seen.add(token)
            params["pageToken"] = token

    def list_calendars(self) -> list[dict]:
        """Read calendar names/IDs only after the user requests the selector."""
        records = self._pages("/users/me/calendarList", {"maxResults": 250, "showHidden": "true", "fields": "items(id,summary,primary),nextPageToken"})
        if any(not isinstance(item.get("id"), str) or not item["id"] for item in records):
            raise GoogleConnectionError("Google returned a calendar without an ID.")
        return records

    def busy_periods(self, calendar_ids: list[str], start: datetime, end: datetime) -> tuple[BusyPeriod, ...]:
        """Fail closed if any selected calendar is inaccessible or incomplete."""
        BusyPeriod(start, end)
        ids = list(dict.fromkeys([*calendar_ids, *([self.connection.calendar_id] if self.connection.calendar_id else [])]))
        if not ids:
            raise GoogleConnectionError("Choose at least one calendar for busy-time checking.")
        busy = []
        for offset in range(0, len(ids), 50):
            batch = ids[offset:offset + 50]
            result = self._call("POST", "/freeBusy", body={
                "timeMin": start.astimezone(timezone.utc).isoformat(), "timeMax": end.astimezone(timezone.utc).isoformat(),
                "calendarExpansionMax": 50, "items": [{"id": key} for key in batch],
            })
            calendars = result.get("calendars")
            if not isinstance(calendars, dict):
                raise GoogleConnectionError("Google busy-time results are incomplete.")
            for key in batch:
                entry = calendars.get(key)
                if not isinstance(entry, dict) or entry.get("errors") or not isinstance(entry.get("busy"), list):
                    raise GoogleConnectionError("Could not read busy times for every selected calendar. Check permissions and try again.")
                try:
                    busy.extend(BusyPeriod(datetime.fromisoformat(item["start"]), datetime.fromisoformat(item["end"])) for item in entry["busy"])
                except (ValueError, TypeError, KeyError):
                    raise GoogleConnectionError("Google returned invalid busy-time intervals.") from None
        return tuple(busy)

    def _events_path(self) -> str:
        if not isinstance(self.connection.calendar_id, str) or not self.connection.calendar_id or self.connection.calendar_id == "primary":
            raise GoogleConnectionError("Select the dedicated planner calendar before exporting.")
        return f"/calendars/{quote(self.connection.calendar_id, safe='')}/events"

    def list_planner_events(self, start: datetime, end: datetime) -> list[dict]:
        return self._pages(self._events_path(), {
            "timeMin": start.isoformat(), "timeMax": end.isoformat(), "singleEvents": "true",
            "maxResults": 2500, "fields": "items(id,status,start,end,extendedProperties),nextPageToken",
        })

    def get_event(self, event_id: str) -> dict | None:
        try:
            return self._call("GET", self._events_path() + "/" + quote(event_id, safe=""))
        except GoogleConnectionError as error:
            if error.status_code == 404:
                return None
            if error.status_code == 410:
                return {"id": event_id, "status": "cancelled"}
            raise

    def insert_event(self, body: dict) -> dict:
        """No patch/delete methods: existing events are never modified by export."""
        return self._call("POST", self._events_path(), body=body, params={"sendUpdates": "none"})
