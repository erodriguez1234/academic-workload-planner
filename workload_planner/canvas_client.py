"""Small read-only Canvas transport; no model conversion or UI behavior.

Construction and environment loading are offline. Only explicit list calls
perform requests. Results contain all API-accessible records for that endpoint,
not a guarantee that Canvas exposes every course or piece of coursework.
"""

import json
import os
import re
from email.message import Message
from http.client import HTTPException, HTTPResponse
from urllib.error import HTTPError, URLError
from urllib.parse import unquote, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener


class CanvasClientError(Exception):
    """A safe retrieval failure, without response bodies or credentials."""


class _NoRedirect(HTTPRedirectHandler):
    """Do not forward the Authorization header to a redirect destination."""

    def redirect_request(
        self, req: Request, fp: HTTPResponse | None, code: int,
        msg: str, headers: Message, newurl: str,
    ) -> None:
        return None


class CanvasClient:
    """Fetch raw course/assignment dictionaries using a personal token.

    base_url is the HTTPS site root, e.g. https://canvas.example.edu.
    Credentials stay in memory; this class never prints or persists responses.
    Each request has a 15-second socket timeout. There are no automatic retries.
    A failed page raises CanvasClientError instead of returning partial data.
    """

    def __init__(self, base_url: str, token: str) -> None:
        try:
            site = urlsplit(base_url)
            valid_site = (
                site.scheme == "https" and bool(site.hostname)
                and not site.username and not site.password
                and site.path in ("", "/") and not site.query and not site.fragment
                and site.port != 0
                and not any(character.isspace() for character in base_url)
            )
        except (ValueError, TypeError, AttributeError):
            valid_site = False
        if not valid_site:
            raise ValueError("base_url must be an HTTPS Canvas site root without credentials or query parameters")
        if not isinstance(token, str) or not token or any(
            character.isspace() or not 33 <= ord(character) <= 126
            for character in token
        ):
            raise ValueError("token must be nonblank text without whitespace or control characters")
        self._base_url = base_url.rstrip("/")
        self._token = token
        self._opener = build_opener(_NoRedirect())

    @classmethod
    def from_environment(cls) -> "CanvasClient":
        """Explicitly read CANVAS_BASE_URL and CANVAS_ACCESS_TOKEN.

        Does not load .env files, create credentials, or contact Canvas.
        Set variables privately outside this application before using it.
        """
        for name in ("CANVAS_BASE_URL", "CANVAS_ACCESS_TOKEN"):
            if not os.environ.get(name):
                raise ValueError(f"Set {name} privately before creating a Canvas client")
        return cls(os.environ["CANVAS_BASE_URL"], os.environ["CANVAS_ACCESS_TOKEN"])

    def list_courses(self) -> list[dict[str, object]]:
        """Return every page of courses Canvas exposes to the current user."""
        return self._list_records("/courses", "courses")

    def list_assignments(self, course_id: int) -> list[dict[str, object]]:
        """Return every accessible assignment page for one selected course.

        No type inference or submitted-work filtering occurs here. Access
        failures identify the selected course; inaccessible work is not skipped.
        """
        if type(course_id) is not int or course_id <= 0:
            raise ValueError("course_id must be a positive integer")
        return self._list_records(
            f"/courses/{course_id}/assignments", f"assignments for course {course_id}",
            "&include%5B%5D=submission&override_assignment_dates=true",
        )

    def list_modules(self, course_id: int) -> list[dict[str, object]]:
        if type(course_id) is not int or course_id <= 0:
            raise ValueError("course_id must be a positive integer")
        return self._list_records(f"/courses/{course_id}/modules", f"modules for course {course_id}")

    def list_module_items(self, course_id: int, module_id: int) -> list[dict[str, object]]:
        if any(type(value) is not int or value <= 0 for value in (course_id, module_id)):
            raise ValueError("course_id and module_id must be positive integers")
        return self._list_records(f"/courses/{course_id}/modules/{module_id}/items", f"items for course {course_id}, module {module_id}")

    def _list_records(
        self, path: str, resource: str, extra_query: str = "",
    ) -> list[dict[str, object]]:
        url = f"{self._base_url}/api/v1{path}?per_page=100{extra_query}"
        records: list[dict[str, object]] = []
        visited: set[str] = set()
        while url:
            if url in visited:
                raise CanvasClientError(f"Could not retrieve {resource}: repeated pagination link; results are incomplete")
            visited.add(url)
            request = Request(url, headers={
                "Authorization": f"Bearer {self._token}",
                "Accept": "application/json",
            }, method="GET")
            try:
                with self._opener.open(request, timeout=15) as response:
                    data = json.loads(response.read())
                    link = response.headers.get("Link", "")
            except HTTPError as error:
                status = error.code
                error.close()
                hints = {
                    401: "check the personal token and its expiration",
                    403: "access denied; check course permissions or token scope",
                    404: "resource not found or not accessible",
                    429: "rate limited; try again later",
                }
                hint = hints.get(status, "Canvas request failed; try again later")
                if 300 <= status < 400:
                    hint = "redirect refused; check the configured Canvas site root"
                raise CanvasClientError(f"Could not retrieve {resource} (HTTP {status}): {hint}; results are incomplete") from None
            except (URLError, OSError, HTTPException):
                raise CanvasClientError(f"Could not retrieve {resource}: connection failed or timed out; results are incomplete") from None
            except (ValueError, UnicodeError):
                raise CanvasClientError(f"Could not retrieve {resource}: invalid JSON response; results are incomplete") from None
            if not isinstance(data, list) or not all(isinstance(item, dict) for item in data):
                raise CanvasClientError(f"Could not retrieve {resource}: expected a list of JSON objects; results are incomplete")
            records.extend(data)
            url = self._next_page(link)
        return records

    def _next_page(self, link: str) -> str:
        """Follow Canvas's opaque next URL only within this HTTPS API origin."""
        if not link:
            return ""
        # Canvas documents comma-separated <URL>; rel="name" entries.
        pattern = r'<([^<>]+)>\s*;\s*rel="([^"]+)"'
        if re.sub(pattern, "", link).strip(" ,\t\r\n"):
            raise CanvasClientError("Invalid Canvas pagination header; results are incomplete")
        next_links = [url for url, relation in re.findall(pattern, link) if "next" in relation.split()]
        if not next_links:
            return ""
        if len(next_links) != 1:
            raise CanvasClientError("Ambiguous Canvas pagination links; results are incomplete")
        url = next_links[0]
        try:
            target = urlsplit(url)
            origin = urlsplit(self._base_url)
            valid = (
                target.scheme == "https" and target.hostname == origin.hostname
                and (target.port or 443) == (origin.port or 443)
                and not target.username and not target.password and not target.fragment
                and target.path.startswith("/api/v1/")
                and not any(part in (".", "..") for part in unquote(target.path).split("/"))
                and not any(character.isspace() or ord(character) < 32 for character in url)
            )
        except ValueError:
            valid = False
        if not valid:
            raise CanvasClientError("Unsafe Canvas pagination link refused; results are incomplete")
        return url
