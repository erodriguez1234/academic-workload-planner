"""Read-only Canvas requests tested entirely with synthetic HTTP responses."""

import io
import json
import traceback
from email.message import Message
from http.client import IncompleteRead
from unittest.mock import Mock
from urllib.error import HTTPError, URLError

import pytest

from workload_planner.canvas_client import CanvasClient, CanvasClientError


BASE_URL = "https://canvas.example.edu"
TOKEN = "synthetic-test-token"


def response(data: object, link: str | None = None) -> Mock:
    """Model the context-managed response returned by urllib's opener."""
    result = Mock()
    result.read.return_value = json.dumps(data).encode("utf-8")
    result.headers = Message()
    if link is not None:
        result.headers["link"] = link
    result.__enter__ = Mock(return_value=result)
    result.__exit__ = Mock(return_value=False)
    return result


@pytest.fixture
def transport(monkeypatch: pytest.MonkeyPatch) -> Mock:
    """Prevent every client in this module from making a network request."""
    opener = Mock()
    monkeypatch.setattr("workload_planner.canvas_client.build_opener", Mock(return_value=opener))
    return opener.open


@pytest.mark.parametrize("resource", ["courses", "assignments"])
def test_reads_every_page_in_order_using_get_and_header_auth(transport: Mock, resource: str) -> None:
    path = "/api/v1/courses" if resource == "courses" else "/api/v1/courses/42/assignments"
    next_url = f"{BASE_URL}{path}?opaque=abc&page=2"
    records = [{"id": 1}, {"id": 2}]
    transport.side_effect = [
        response(records[:1], f'<{next_url}>; rel="next", <{BASE_URL}{path}>; rel="first"'),
        response(records[1:]),
    ]
    client = CanvasClient(BASE_URL + "/", TOKEN)
    assert transport.call_count == 0  # Construction is offline.

    actual = client.list_courses() if resource == "courses" else client.list_assignments(42)

    assert actual == records
    assert transport.call_count == 2
    first, second = [call.args[0] for call in transport.call_args_list]
    query = "per_page=100"
    if resource == "assignments":
        query += "&include%5B%5D=submission&override_assignment_dates=true"
    assert first.full_url == f"{BASE_URL}{path}?{query}"
    assert second.full_url == next_url  # Opaque pagination parameters stay intact.
    for call in transport.call_args_list:
        request = call.args[0]
        assert request.get_method() == "GET"
        assert request.get_header("Authorization") == f"Bearer {TOKEN}"
        assert TOKEN not in request.full_url
        assert call.kwargs["timeout"] == 15


def test_empty_page_can_still_have_a_next_page(transport: Mock) -> None:
    transport.side_effect = [
        response([], f'<{BASE_URL}/api/v1/courses?page=2>; rel="next"'),
        response([{"id": 3}]),
    ]
    assert CanvasClient(BASE_URL, TOKEN).list_courses() == [{"id": 3}]


@pytest.mark.parametrize("status, hint", [(401, "token"), (403, "access"), (404, "found"), (429, "later"), (500, "later"), (302, "redirect")])
def test_http_failures_are_safe_and_do_not_return_partial_results(transport: Mock, status: int, hint: str) -> None:
    transport.side_effect = [
        response([{"id": 1}], f'<{BASE_URL}/api/v1/courses?page=2>; rel="next"'),
        HTTPError(f"{BASE_URL}/?{TOKEN}", status, TOKEN, {}, io.BytesIO(b"private body")),
    ]
    with pytest.raises(CanvasClientError) as caught:
        CanvasClient(BASE_URL, TOKEN).list_courses()
    assert str(status) in str(caught.value)
    assert hint in str(caught.value).lower()
    assert TOKEN not in "".join(traceback.format_exception(caught.value))
    assert "private body" not in str(caught.value)


@pytest.mark.parametrize("error", [URLError(TOKEN), TimeoutError(TOKEN), OSError(TOKEN), IncompleteRead(b"private body")])
def test_connection_failures_do_not_expose_original_exception(transport: Mock, error: Exception) -> None:
    transport.side_effect = error
    with pytest.raises(CanvasClientError, match="connection") as caught:
        CanvasClient(BASE_URL, TOKEN).list_courses()
    assert TOKEN not in "".join(traceback.format_exception(caught.value))


@pytest.mark.parametrize("payload", [{"errors": "private"}, [1], [None], "private"])
def test_rejects_non_list_or_non_object_records(transport: Mock, payload: object) -> None:
    transport.return_value = response(payload)
    with pytest.raises(CanvasClientError, match="list of JSON objects"):
        CanvasClient(BASE_URL, TOKEN).list_courses()


def test_invalid_json_is_reported_without_response_body(transport: Mock) -> None:
    transport.return_value = response([])
    transport.return_value.read.return_value = TOKEN.encode()
    with pytest.raises(CanvasClientError, match="JSON") as caught:
        CanvasClient(BASE_URL, TOKEN).list_courses()
    assert TOKEN not in "".join(traceback.format_exception(caught.value))


def test_invalid_utf8_response_is_reported(transport: Mock) -> None:
    transport.return_value = response([])
    transport.return_value.read.return_value = b"\xff"
    with pytest.raises(CanvasClientError, match="JSON"):
        CanvasClient(BASE_URL, TOKEN).list_courses()


@pytest.mark.parametrize("link", [
    "not a valid link",
    f'<{BASE_URL}/api/v1/courses?page=2>; rel="next", broken',
    f'<{BASE_URL}/api/v1/courses?page=2>; rel="next", <{BASE_URL}/api/v1/courses?page=3>; rel="next"',
])
def test_malformed_or_ambiguous_pagination_does_not_silently_truncate(transport: Mock, link: str) -> None:
    transport.return_value = response([{"id": 1}], link)
    with pytest.raises(CanvasClientError, match="pagination"):
        CanvasClient(BASE_URL, TOKEN).list_courses()
    assert transport.call_count == 1


def test_access_gap_identifies_selected_course_without_private_body(transport: Mock) -> None:
    transport.side_effect = HTTPError(BASE_URL, 403, "private", {}, io.BytesIO(b"private"))
    with pytest.raises(CanvasClientError, match="course 42.*403.*access"):
        CanvasClient(BASE_URL, TOKEN).list_assignments(42)


@pytest.mark.parametrize("url", [
    "https://elsewhere.example/api/v1/courses?page=2",
    "http://canvas.example.edu/api/v1/courses?page=2",
    "https://canvas.example.edu:444/api/v1/courses?page=2",
    "https://user@canvas.example.edu/api/v1/courses?page=2",
    "https://canvas.example.edu/login",
    "https://canvas.example.edu/api/v1/../login",
])
def test_unsafe_pagination_is_rejected_before_another_request(transport: Mock, url: str) -> None:
    transport.return_value = response([], f'<{url}>; rel="next"')
    with pytest.raises(CanvasClientError, match="pagination"):
        CanvasClient(BASE_URL, TOKEN).list_courses()
    assert transport.call_count == 1


def test_repeated_pagination_link_is_reported_instead_of_looping(transport: Mock) -> None:
    transport.return_value = response([], f'<{BASE_URL}/api/v1/courses?per_page=100>; rel="next"')
    with pytest.raises(CanvasClientError, match="pagination"):
        CanvasClient(BASE_URL, TOKEN).list_courses()
    assert transport.call_count == 1


@pytest.mark.parametrize("url", ["http://canvas.example.edu", "https://user:password@canvas.example.edu", BASE_URL + "/api/v1", BASE_URL + "?token=private", "", "https://canvas.example.edu:bad"])
def test_base_url_must_be_an_https_site_root(transport: Mock, url: str) -> None:
    with pytest.raises(ValueError, match="base_url"):
        CanvasClient(url, TOKEN)
    transport.assert_not_called()


@pytest.mark.parametrize("token", ["", "  ", "bad\ntoken", "bad\rtoken", "bad token"])
def test_rejects_blank_or_unsafe_tokens(transport: Mock, token: str) -> None:
    with pytest.raises(ValueError, match="token"):
        CanvasClient(BASE_URL, token)
    transport.assert_not_called()


@pytest.mark.parametrize("course_id", [True, 0, -1, "42", "../courses"])
def test_course_id_must_be_a_positive_integer(transport: Mock, course_id: object) -> None:
    with pytest.raises(ValueError, match="course_id"):
        CanvasClient(BASE_URL, TOKEN).list_assignments(course_id)
    transport.assert_not_called()


def test_environment_configuration_is_explicit_and_offline(transport: Mock, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CANVAS_BASE_URL", BASE_URL)
    monkeypatch.setenv("CANVAS_ACCESS_TOKEN", TOKEN)
    client = CanvasClient.from_environment()
    assert TOKEN not in repr(client)
    transport.assert_not_called()
    transport.return_value = response([])
    assert client.list_courses() == []


@pytest.mark.parametrize("missing", ["CANVAS_BASE_URL", "CANVAS_ACCESS_TOKEN"])
def test_missing_environment_configuration_has_readable_error(transport: Mock, monkeypatch: pytest.MonkeyPatch, missing: str) -> None:
    monkeypatch.setenv("CANVAS_BASE_URL", BASE_URL)
    monkeypatch.setenv("CANVAS_ACCESS_TOKEN", TOKEN)
    monkeypatch.delenv(missing)
    with pytest.raises(ValueError, match=missing):
        CanvasClient.from_environment()
    transport.assert_not_called()


def test_default_transport_blocks_redirects() -> None:
    """Exercise urllib's actual redirect policy without opening a connection."""
    from urllib.request import HTTPRedirectHandler, Request

    client = CanvasClient(BASE_URL, TOKEN)
    handlers = [handler for handler in client._opener.handlers if isinstance(handler, HTTPRedirectHandler)]
    assert len(handlers) == 1
    assert handlers[0].redirect_request(Request(BASE_URL), None, 302, "Found", Message(), "https://elsewhere.example") is None
