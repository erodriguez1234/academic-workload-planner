"""Suggested current planning dates, separate from fixed sample-demo dates."""

from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo


def current_planning_dates(
    zone_name: str, *, now: datetime | None = None,
) -> tuple[date, time, date]:
    """Suggest the next whole minute and a 14-day inclusive local horizon.

    The optional clock makes tests repeatable. These are editable UI defaults;
    the scheduler still receives an explicit planning start, not a live clock.
    """
    zone = ZoneInfo(zone_name.strip())
    if now is None:
        now = datetime.now(timezone.utc)
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("now must include timezone information")
    start = (now.astimezone(timezone.utc) + timedelta(minutes=1)).replace(second=0, microsecond=0).astimezone(zone)
    return start.date(), start.time().replace(tzinfo=None), start.date() + timedelta(days=13)
