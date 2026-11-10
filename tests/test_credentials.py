"""Credential storage contracts; never use the real macOS Keychain in tests."""

import traceback
from unittest.mock import Mock

import pytest
from keyring.errors import KeyringError

from workload_planner import credentials


@pytest.fixture
def backend(monkeypatch: pytest.MonkeyPatch) -> Mock:
    store = Mock()
    store.get_password.return_value = None
    monkeypatch.setattr(credentials, "_backend", lambda: store)
    return store


def test_round_trip_and_canonical_site_key(backend: Mock) -> None:
    credentials.save_token("https://Canvas.example.edu/", "synthetic-token")
    backend.set_password.assert_called_once()
    service, account, token = backend.set_password.call_args.args
    assert token == "synthetic-token"
    backend.get_password.return_value = token
    assert credentials.load_token("https://canvas.example.edu:443") == token
    backend.get_password.assert_called_once_with(service, account)


def test_tokens_for_different_sites_have_separate_keys(backend: Mock) -> None:
    credentials.load_token("https://one.example.edu")
    credentials.load_token("https://two.example.edu")
    assert backend.get_password.call_args_list[0] != backend.get_password.call_args_list[1]


def test_forget_deletes_only_selected_site(backend: Mock) -> None:
    backend.get_password.return_value = "synthetic-token"
    credentials.forget_token("https://canvas.example.edu")
    backend.delete_password.assert_called_once_with(*backend.get_password.call_args.args)


def test_forget_is_harmless_when_no_token_is_saved(backend: Mock) -> None:
    credentials.forget_token("https://canvas.example.edu")
    backend.delete_password.assert_not_called()


@pytest.mark.parametrize("operation", ["load_token", "save_token", "forget_token"])
def test_keychain_failure_does_not_expose_original_error(backend: Mock, operation: str) -> None:
    private_error = KeyringError("synthetic-private-token")
    backend.get_password.side_effect = private_error
    backend.set_password.side_effect = private_error
    args = ["https://canvas.example.edu"]
    if operation == "save_token":
        args.append("synthetic-token")
    with pytest.raises(credentials.CredentialStoreError, match="Keychain") as caught:
        getattr(credentials, operation)(*args)
    assert "synthetic-private-token" not in "".join(traceback.format_exception(caught.value))


@pytest.mark.parametrize("site", ["http://canvas.example.edu", "https://user:password@canvas.example.edu", "https://canvas.example.edu/login", "https://canvas.example.edu?token=private"])
def test_invalid_sites_do_not_access_keychain(backend: Mock, site: str) -> None:
    with pytest.raises(ValueError):
        credentials.load_token(site)
    backend.get_password.assert_not_called()


def test_google_state_is_separate_from_canvas_and_scoped_to_client(backend: Mock) -> None:
    credentials.save_google_state("client-one", "synthetic-state")
    service, account, _ = backend.set_password.call_args.args
    backend.get_password.return_value = "synthetic-state"
    assert credentials.load_google_state("client-one") == "synthetic-state"
    backend.get_password.assert_called_with(service, account)
    credentials.load_google_state("client-two")
    assert backend.get_password.call_args.args[0] != service
    credentials.forget_google_state("client-one")
    backend.delete_password.assert_called_once_with(service, account)


@pytest.mark.parametrize("operation", ["load_google_state", "save_google_state", "forget_google_state"])
def test_google_keychain_errors_hide_backend_details(backend: Mock, operation: str) -> None:
    backend.get_password.side_effect = KeyringError("synthetic-private-value")
    backend.set_password.side_effect = KeyringError("synthetic-private-value")
    args = ["client"] + (["synthetic-state"] if operation == "save_google_state" else [])
    with pytest.raises(credentials.CredentialStoreError) as caught:
        getattr(credentials, operation)(*args)
    assert "synthetic-private-value" not in "".join(traceback.format_exception(caught.value))
