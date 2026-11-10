"""Explicit local Google OAuth, with refresh credentials stored in Keychain."""

import json
import logging
from dataclasses import dataclass, field
from functools import partial
from pathlib import Path
from uuid import uuid4

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google.oauth2.id_token import verify_oauth2_token
from google_auth_oauthlib.flow import InstalledAppFlow

from workload_planner.credentials import (
    CredentialStoreError, forget_google_state, load_google_state, save_google_state,
)

CLIENT_PATH = Path(__file__).resolve().parents[1] / ".local" / "google_oauth_client.json"
SCOPES = (
    "https://www.googleapis.com/auth/calendar.app.created", "openid",
    "https://www.googleapis.com/auth/calendar.calendarlist.readonly",
    "https://www.googleapis.com/auth/calendar.events.freebusy",
)

# The SDK's callback logger can include an authorization code in the request URL.
# Neither callback URLs nor token-exchange payloads belong in the app's logs.
logging.getLogger("google_auth_oauthlib.flow").disabled = True
logging.getLogger("requests_oauthlib.oauth2_session").disabled = True


class GoogleConnectionError(Exception):
    """A user-facing connection/access error with no underlying secrets."""

    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


def _client_config(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise GoogleConnectionError("Put the downloaded Desktop OAuth JSON in .local/google_oauth_client.json.") from None
    except (OSError, ValueError, UnicodeError):
        raise GoogleConnectionError("Could not read the Desktop OAuth client JSON. Check its format and file permissions.") from None
    config = data.get("installed") if isinstance(data, dict) else None
    if not isinstance(config, dict) or not all(isinstance(config.get(key), str) and config[key] for key in ("client_id", "client_secret", "auth_uri", "token_uri")):
        raise GoogleConnectionError("Use a downloaded Google OAuth Desktop client JSON, not a Web client or API key.")
    if config["auth_uri"] != "https://accounts.google.com/o/oauth2/auth" or config["token_uri"] != "https://oauth2.googleapis.com/token":
        raise GoogleConnectionError("The Desktop configuration must use Google's official OAuth endpoints.")
    return data


@dataclass(repr=False)
class GoogleConnection:
    """One local connection; calendar metadata stays bound to its credentials."""

    credentials: Credentials
    client_id: str
    calendar_id: str | None = None
    marker: str = field(default_factory=lambda: uuid4().hex)
    creation_pending: bool = False
    subject: str | None = None

    def persist(self) -> None:
        try:
            save_google_state(self.client_id, json.dumps({
                "credentials": json.loads(self.credentials.to_json()),
                "calendar_id": self.calendar_id, "marker": self.marker,
                "creation_pending": self.creation_pending,
                "subject": self.subject,
            }))
        except (CredentialStoreError, ValueError, TypeError):
            raise GoogleConnectionError("Google connection state could not be saved in Keychain. Unlock Keychain and reconnect.") from None

    def ensure_fresh(self) -> None:
        """Renew expired authorization without reopening the browser."""
        if self.credentials.valid:
            return
        if not self.credentials.refresh_token:
            raise GoogleConnectionError("Google authorization is no longer valid. Use Authorize Google again.")
        try:
            self.credentials.refresh(partial(Request(), timeout=20))
        except Exception:
            raise GoogleConnectionError("Google authorization could not be renewed. Check your connection or use Authorize Google again.") from None
        if not self.credentials.valid:
            raise GoogleConnectionError("Google authorization is no longer valid. Use Authorize Google again.")
        self.persist()


def _saved_state(raw: str, client_id: str) -> dict:
    """Validate private stored fields before restoring or reusing a calendar."""
    try:
        state = json.loads(raw)
        info = state["credentials"]
        calendar_id = state.get("calendar_id")
        marker = state.get("marker", uuid4().hex)
        pending = state.get("creation_pending", False)
        subject = state.get("subject")
        if (
            not isinstance(info, dict) or info.get("client_id", client_id) != client_id
            or (calendar_id is not None and (not isinstance(calendar_id, str) or not calendar_id.strip() or calendar_id == "primary"))
            or not isinstance(marker, str) or not marker.strip() or type(pending) is not bool
            or (subject is not None and (not isinstance(subject, str) or not subject))
        ):
            raise ValueError("invalid saved state")
        state["marker"] = marker
        return state
    except (ValueError, KeyError, TypeError):
        raise GoogleConnectionError("The saved Google connection is invalid. Use Authorize Google again.") from None


def connect_google(path: Path | None = None, *, reauthorize: bool = False, allow_interactive: bool = True) -> GoogleConnection:
    """Reuse/renew saved access or, on explicit request, open the local browser flow.

    A verified OpenID subject preserves a calendar only for the same account.
    Switching accounts starts a fresh connection. Existing calendars remain.
    """
    config = _client_config(CLIENT_PATH if path is None else path)
    client_id = config["installed"]["client_id"]
    try:
        raw = load_google_state(client_id)
        try:
            state = _saved_state(raw, client_id) if raw else None
        except GoogleConnectionError:
            if not reauthorize:
                raise
            state = None
        if state and not reauthorize:
            try:
                credentials = Credentials.from_authorized_user_info(state["credentials"])
                connection = GoogleConnection(
                    credentials, client_id, state.get("calendar_id"), state["marker"],
                    state.get("creation_pending", False), state.get("subject"),
                )
            except (ValueError, KeyError, TypeError):
                raise GoogleConnectionError("The saved Google connection is invalid. Use Authorize Google again.") from None
        else:
            if not allow_interactive:
                raise GoogleConnectionError("No saved Google authorization is available. Connect Google Calendar to sign in.")
            try:
                flow = InstalledAppFlow.from_client_config(config, scopes=SCOPES, autogenerate_code_verifier=True)
                flow.oauth2session.request = partial(flow.oauth2session.request, timeout=20)
                credentials = flow.run_local_server(
                    host="127.0.0.1", port=0, open_browser=True, timeout_seconds=120,
                    authorization_prompt_message="",
                    success_message="Authorization received. Return to Academic Workload Planner. If the app reports an error, retry there.",
                    prompt="consent select_account", access_type="offline",
                )
            except Exception:
                raise GoogleConnectionError("Google authorization was cancelled, timed out, or failed. Retry; check your test-user list and school account policy if Google blocks access.") from None
            if not credentials.refresh_token:
                raise GoogleConnectionError("Google did not provide renewable authorization. Authorize Google again and approve Calendar access.")
            try:
                claims = verify_oauth2_token(credentials.id_token, partial(Request(), timeout=20), audience=client_id)
                subject = claims["sub"]
                if not isinstance(subject, str) or not subject:
                    raise ValueError("missing identity")
            except Exception:
                raise GoogleConnectionError("Google identity could not be verified. Authorize Google again.") from None
            connection = GoogleConnection(credentials, client_id, subject=subject)
            if state and state.get("subject") == subject:
                connection.calendar_id = state.get("calendar_id")
                connection.marker = state["marker"]
                connection.creation_pending = state.get("creation_pending", False)
        if not credentials.has_scopes(SCOPES) or (credentials.granted_scopes is not None and not set(SCOPES).issubset(credentials.granted_scopes)):
            raise GoogleConnectionError("Required Calendar permissions are missing. Authorize Google again and approve app-created calendars, calendar-list access, and calendar availability access.")
        if connection.credentials.valid:
            connection.persist()
        else:
            connection.ensure_fresh()
        return connection
    except CredentialStoreError:
        raise GoogleConnectionError("Google authorization could not be read from Keychain. Unlock it and try again.") from None


def forget_google(path: Path | None = None) -> None:
    """Remove local saved authorization only; remote calendars are untouched."""
    config = _client_config(CLIENT_PATH if path is None else path)
    try:
        forget_google_state(config["installed"]["client_id"])
    except CredentialStoreError:
        raise GoogleConnectionError("Could not forget Google authorization. Unlock Keychain and try again.") from None
