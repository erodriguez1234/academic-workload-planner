"""Local OAuth behavior without browsers, tokens, or real Keychain access."""

import json
import traceback
from pathlib import Path
from unittest.mock import Mock

import pytest

from workload_planner import google_auth


@pytest.fixture
def config(tmp_path: Path) -> Path:
    path = tmp_path / "client.json"
    path.write_text(json.dumps({"installed": {
        "client_id": "synthetic.apps.googleusercontent.com", "client_secret": "synthetic-secret",
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
    }}))
    return path


@pytest.fixture
def auth(monkeypatch: pytest.MonkeyPatch) -> tuple[Mock, Mock, Mock, Mock]:
    creds = Mock(valid=True, refresh_token="synthetic-refresh", granted_scopes=None)
    creds.has_scopes.return_value = True
    creds.to_json.return_value = '{"token":"synthetic-access","refresh_token":"synthetic-refresh"}'
    flow = Mock()
    flow.run_local_server.return_value = creds
    factory = Mock(return_value=flow)
    monkeypatch.setattr(google_auth.InstalledAppFlow, "from_client_config", factory)
    load, save = Mock(return_value=None), Mock()
    monkeypatch.setattr(google_auth, "load_google_state", load)
    monkeypatch.setattr(google_auth, "save_google_state", save)
    monkeypatch.setattr(google_auth.Credentials, "from_authorized_user_info", Mock(return_value=creds))
    monkeypatch.setattr(google_auth, "verify_oauth2_token", Mock(return_value={"sub": "synthetic-user"}))
    return creds, factory, load, save


def test_first_connect_opens_local_oauth_with_pkce_and_persists(config: Path, auth: tuple) -> None:
    connection = google_auth.connect_google(config)
    creds, factory, _, save = auth
    assert connection.credentials is creds
    assert factory.call_args.kwargs["autogenerate_code_verifier"] is True
    options = factory.return_value.run_local_server.call_args.kwargs
    assert options["host"] == "127.0.0.1" and options["port"] == 0
    assert options["timeout_seconds"] == 120 and options["open_browser"] is True
    assert options["authorization_prompt_message"] == ""
    assert options["prompt"] == "consent select_account"
    assert save.call_count == 1
    assert "synthetic-access" not in repr(connection)


def test_saved_valid_authorization_reconnects_without_browser(config: Path, auth: tuple) -> None:
    creds, factory, load, _ = auth
    load.return_value = json.dumps({"credentials": {}, "calendar_id": "planner-id", "marker": "marker", "creation_pending": False})
    connection = google_auth.connect_google(config)
    assert connection.calendar_id == "planner-id"
    factory.assert_not_called()
    creds.refresh.assert_not_called()


def test_saved_expired_credentials_refresh_and_persist(config: Path, auth: tuple) -> None:
    creds, factory, load, save = auth
    load.return_value = '{"credentials":{}}'
    creds.valid = False
    creds.refresh.side_effect = lambda request: setattr(creds, "valid", True)
    google_auth.connect_google(config)
    creds.refresh.assert_called_once()
    factory.assert_not_called()
    save.assert_called_once()


def test_revoked_authorization_requests_reconnection_without_leaking_error(config: Path, auth: tuple) -> None:
    creds, factory, load, _ = auth
    load.return_value = '{"credentials":{}}'
    creds.valid = False
    creds.refresh.side_effect = RuntimeError("synthetic-private-token")
    with pytest.raises(google_auth.GoogleConnectionError, match="[Aa]uthorize") as caught:
        google_auth.connect_google(config)
    assert "synthetic-private-token" not in "".join(traceback.format_exception(caught.value))
    factory.assert_not_called()


def test_explicit_reauthorization_does_not_reuse_previous_account_calendar(config: Path, auth: tuple) -> None:
    _, factory, load, _ = auth
    load.return_value = '{"credentials":{},"calendar_id":"old-account"}'
    connection = google_auth.connect_google(config, reauthorize=True)
    assert connection.calendar_id is None
    factory.assert_called_once()


def test_same_account_reauthorization_keeps_its_calendar(config: Path, auth: tuple) -> None:
    auth[2].return_value = json.dumps({"credentials": {}, "subject": "synthetic-user", "calendar_id": "planner-id", "marker": "saved-marker"})
    connection = google_auth.connect_google(config, reauthorize=True)
    assert connection.calendar_id == "planner-id" and connection.marker == "saved-marker"


def test_identity_verification_failure_is_not_saved(config: Path, auth: tuple, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(google_auth, "verify_oauth2_token", Mock(side_effect=ValueError("synthetic-private-value")))
    with pytest.raises(google_auth.GoogleConnectionError, match="identity"):
        google_auth.connect_google(config)
    auth[3].assert_not_called()


@pytest.mark.parametrize("failure", [TimeoutError("private"), RuntimeError("private")])
def test_cancelled_or_failed_sign_in_has_safe_message(config: Path, auth: tuple, failure: Exception) -> None:
    auth[1].return_value.run_local_server.side_effect = failure
    with pytest.raises(google_auth.GoogleConnectionError, match="authorization") as caught:
        google_auth.connect_google(config)
    assert "private" not in str(caught.value)


def test_missing_calendar_permission_is_not_saved(config: Path, auth: tuple) -> None:
    auth[0].granted_scopes = ["openid"]
    with pytest.raises(google_auth.GoogleConnectionError, match="permission"):
        google_auth.connect_google(config)
    auth[3].assert_not_called()


@pytest.mark.parametrize("body", ["invalid", "{}", '{"web":{}}'])
def test_invalid_config_reports_setup_error_without_browser(tmp_path: Path, auth: tuple, body: str) -> None:
    path = tmp_path / "bad.json"
    path.write_text(body)
    with pytest.raises(google_auth.GoogleConnectionError, match="Desktop"):
        google_auth.connect_google(path)
    auth[1].assert_not_called()


def test_missing_config_has_local_path_guidance(tmp_path: Path, auth: tuple) -> None:
    with pytest.raises(google_auth.GoogleConnectionError, match="google_oauth_client.json"):
        google_auth.connect_google(tmp_path / "missing.json")


def test_corrupt_saved_state_is_not_silently_replaced(config: Path, auth: tuple) -> None:
    auth[2].return_value = "not JSON"
    with pytest.raises(google_auth.GoogleConnectionError, match="saved"):
        google_auth.connect_google(config)
    auth[1].assert_not_called()
    auth[3].assert_not_called()


def test_real_sdk_credentials_round_trip_offline(config: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from datetime import datetime
    from google.oauth2.credentials import Credentials

    creds = Credentials(
        token="synthetic-access", refresh_token="synthetic-refresh",
        client_id="synthetic.apps.googleusercontent.com", client_secret="synthetic-secret",
        token_uri="https://oauth2.googleapis.com/token", scopes=google_auth.SCOPES,
        expiry=datetime(2099, 1, 1),
    )
    state = json.dumps({"credentials": json.loads(creds.to_json()), "calendar_id": "planner-id", "marker": "synthetic-marker"})
    monkeypatch.setattr(google_auth, "load_google_state", Mock(return_value=state))
    save = Mock()
    monkeypatch.setattr(google_auth, "save_google_state", save)
    monkeypatch.setattr(google_auth.InstalledAppFlow, "from_client_config", Mock(side_effect=AssertionError("no browser expected")))
    connection = google_auth.connect_google(config)
    assert connection.credentials.valid and connection.calendar_id == "planner-id"
    restored = json.loads(save.call_args.args[1])
    assert restored["credentials"]["refresh_token"] == "synthetic-refresh"
    assert restored["marker"] == "synthetic-marker"


def test_real_sdk_generates_state_and_pkce_without_network(config: Path) -> None:
    from urllib.parse import parse_qs, urlsplit

    flow = google_auth.InstalledAppFlow.from_client_config(
        json.loads(config.read_text()), scopes=google_auth.SCOPES, autogenerate_code_verifier=True,
    )
    flow.redirect_uri = "http://127.0.0.1:12345/"
    url, state = flow.authorization_url(prompt="consent select_account", access_type="offline")
    parameters = parse_qs(urlsplit(url).query)
    assert parameters["code_challenge_method"] == ["S256"]
    assert parameters["state"] == [state] and state
    assert parameters["scope"] == [" ".join(google_auth.SCOPES)]
    assert parameters["redirect_uri"] == [flow.redirect_uri]


def test_old_saved_scopes_require_explicit_reauthorization(config: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from datetime import datetime
    from google.oauth2.credentials import Credentials

    old = Credentials(token="synthetic", refresh_token="synthetic", client_id="synthetic.apps.googleusercontent.com",
                      client_secret="synthetic", token_uri="https://oauth2.googleapis.com/token",
                      scopes=("openid", "https://www.googleapis.com/auth/calendar.app.created"), expiry=datetime(2099, 1, 1))
    state = json.dumps({"credentials": json.loads(old.to_json()), "marker": "owner", "subject": "user"})
    monkeypatch.setattr(google_auth, "load_google_state", Mock(return_value=state))
    save = Mock()
    monkeypatch.setattr(google_auth, "save_google_state", save)
    with pytest.raises(google_auth.GoogleConnectionError, match="Authorize Google again"):
        google_auth.connect_google(config)
    save.assert_not_called()


def test_noninteractive_resume_never_opens_browser_when_saved_state_is_missing(config: Path, auth: tuple) -> None:
    with pytest.raises(google_auth.GoogleConnectionError, match="No saved Google authorization"):
        google_auth.connect_google(config, allow_interactive=False)
    auth[1].assert_not_called()
    auth[3].assert_not_called()


def test_noninteractive_resume_renews_existing_authorization(config: Path, auth: tuple) -> None:
    creds, factory, load, save = auth
    load.return_value = '{"credentials":{},"subject":"synthetic-user"}'
    creds.valid = False
    creds.refresh.side_effect = lambda request: setattr(creds, "valid", True)
    connection = google_auth.connect_google(config, allow_interactive=False)
    assert connection.credentials.valid
    creds.refresh.assert_called_once()
    factory.assert_not_called()
    save.assert_called_once()


@pytest.mark.parametrize("extra", [
    {"calendar_id": []}, {"calendar_id": "primary"},
    {"creation_pending": "yes"}, {"marker": 123},
])
def test_invalid_saved_calendar_metadata_requires_reconnection(config: Path, auth: tuple, extra: dict) -> None:
    auth[2].return_value = json.dumps({"credentials": {}, **extra})
    with pytest.raises(google_auth.GoogleConnectionError, match="saved"):
        google_auth.connect_google(config)
    auth[3].assert_not_called()
