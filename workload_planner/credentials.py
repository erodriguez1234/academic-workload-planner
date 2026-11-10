"""Opt-in Canvas token persistence in macOS Keychain, outside project files."""

import sys
from hashlib import sha256
from urllib.parse import urlsplit

from keyring.backend import KeyringBackend
from keyring.errors import KeyringError

ACCOUNT = "canvas-personal-access-token"


class CredentialStoreError(Exception):
    """Safe storage error without a credential or backend exception payload."""


def _backend() -> KeyringBackend:
    """Use the native macOS backend explicitly; never fall back to a file."""
    if sys.platform != "darwin":
        raise CredentialStoreError("Remembering tokens requires macOS Keychain on this computer.")
    from keyring.backends.macOS import Keyring

    return Keyring()


def _service(site_url: str) -> str:
    """Scope a saved token to one canonical HTTPS Canvas site."""
    try:
        site = urlsplit(site_url)
        valid = (
            site.scheme == "https" and bool(site.hostname)
            and not site.username and not site.password
            and site.path in ("", "/") and not site.query and not site.fragment
            and not any(character.isspace() for character in site_url)
            and site.port != 0
        )
        port = f":{site.port}" if site.port not in (None, 443) else ""
    except ValueError:
        valid = False
    if not valid:
        raise ValueError("Canvas site must be an HTTPS site root without credentials or query parameters")
    return f"Academic Workload Planner / Canvas / https://{site.hostname}{port}"


def load_token(site_url: str) -> str | None:
    """Read only after an explicit connection action; never populate a widget."""
    service = _service(site_url)
    try:
        return _backend().get_password(service, ACCOUNT)
    except (KeyringError, OSError, RuntimeError):
        raise CredentialStoreError("Could not read macOS Keychain. Unlock it or enter a token for this session.") from None


def save_token(site_url: str, token: str) -> None:
    """Save or replace a token only after the student opts in and connects."""
    service = _service(site_url)
    if not isinstance(token, str) or not token or any(character.isspace() for character in token):
        raise ValueError("Token must be nonblank text without whitespace")
    try:
        _backend().set_password(service, ACCOUNT, token)
    except (KeyringError, OSError, RuntimeError):
        raise CredentialStoreError("Could not save the token in macOS Keychain. This session can still use Canvas.") from None


def forget_token(site_url: str) -> None:
    """Delete only the planner's token for this site; missing is already forgotten."""
    service = _service(site_url)
    try:
        backend = _backend()
        if backend.get_password(service, ACCOUNT) is not None:
            backend.delete_password(service, ACCOUNT)
    except (KeyringError, OSError, RuntimeError):
        raise CredentialStoreError("Could not remove the token from macOS Keychain. Unlock it and try again.") from None


def _google_service(client_id: str) -> str:
    return "Academic Workload Planner / Google / " + sha256(client_id.encode()).hexdigest()


def load_google_state(client_id: str) -> str | None:
    """Read an OAuth/calendar-state envelope only on an explicit connection."""
    try:
        return _backend().get_password(_google_service(client_id), "calendar-authorization")
    except (KeyringError, OSError, RuntimeError):
        raise CredentialStoreError("Could not read Google authorization from macOS Keychain.") from None


def save_google_state(client_id: str, state: str) -> None:
    """Keep refresh credentials and the dedicated calendar ID out of project files."""
    try:
        _backend().set_password(_google_service(client_id), "calendar-authorization", state)
    except (KeyringError, OSError, RuntimeError):
        raise CredentialStoreError("Could not save Google authorization in macOS Keychain.") from None


def forget_google_state(client_id: str) -> None:
    """Forget this client's local authorization; do not delete remote calendars."""
    try:
        backend = _backend()
        service = _google_service(client_id)
        if backend.get_password(service, "calendar-authorization") is not None:
            backend.delete_password(service, "calendar-authorization")
    except (KeyringError, OSError, RuntimeError):
        raise CredentialStoreError("Could not remove Google authorization from macOS Keychain.") from None
