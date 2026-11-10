"""Presentation-only date/time formatting shared by the Streamlit views."""

from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


def format_datetime(value: datetime | None, timezone_name: str | None = None) -> str:
    """Show month names and AM/PM, retaining a timezone label.

    Convert only the displayed copy to the student's timezone. While an invalid
    timezone is being edited, keep the source timezone; generation handles the
    validation error. No scheduler input or stored timestamp is changed.
    """
    if value is None:
        return "No deadline"
    if timezone_name is not None:
        try:
            value = value.astimezone(ZoneInfo(timezone_name.strip()))
        except (ZoneInfoNotFoundError, ValueError):
            pass
    clock = value.strftime("%I:%M%p").lstrip("0")
    return f"{value:%B} {value.day}, {value.year} {clock} {value:%Z}".rstrip()
