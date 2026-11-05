"""Expand student-local weekly windows into bounded, dated availability."""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from workload_planner.scheduling_models import AvailabilityPeriod


@dataclass(frozen=True)
class WeeklyAvailability:
    """Monday=0 through Sunday=6; an earlier end time means the next day."""

    weekday: int
    start_time: time
    end_time: time

    def __post_init__(self) -> None:
        if isinstance(self.weekday, bool) or not isinstance(self.weekday, int):
            raise TypeError("weekday must be an integer")
        if not 0 <= self.weekday <= 6:
            raise ValueError("weekday must be between 0 (Monday) and 6 (Sunday)")
        for name, value in (("start_time", self.start_time), ("end_time", self.end_time)):
            if not isinstance(value, time):
                raise TypeError(f"{name} must be a time")
            if value.tzinfo is not None or value.second or value.microsecond:
                raise ValueError(f"{name} must be a local time in whole minutes")
        if self.start_time == self.end_time:
            raise ValueError("Study window start and end times must differ")


def localize_datetime(local: datetime, zone: ZoneInfo) -> datetime:
    """Attach a timezone, rejecting ambiguous or nonexistent local clock times.

    Round-trip through UTC to detect a spring-forward gap. Different valid UTC
    offsets for fold=0/1 identify a repeated fall-back time. Ask the student to
    choose another time rather than silently guessing which instant they mean.
    """
    if not isinstance(local, datetime) or local.tzinfo is not None:
        raise TypeError("local must be a datetime without timezone information")
    if not isinstance(zone, ZoneInfo):
        raise TypeError("zone must be a ZoneInfo")
    first = local.replace(tzinfo=zone, fold=0)
    second = local.replace(tzinfo=zone, fold=1)
    valid = [
        candidate for candidate in (first, second)
        if candidate.astimezone(timezone.utc).astimezone(zone).replace(tzinfo=None) == local
    ]
    if not valid or (len(valid) == 2 and first.utcoffset() != second.utcoffset()):
        raise ValueError(
            f"{local:%Y-%m-%d %H:%M} in {zone.key} is ambiguous or nonexistent "
            "during a clock change. Choose a different time."
        )
    return valid[0]


def expand_weekly_availability(
    rules: Sequence[WeeklyAvailability],
    start_date: date,
    end_date: date,
    zone: ZoneInfo,
) -> list[AvailabilityPeriod]:
    """Expand into chronological periods inside an inclusive date horizon.

    Limit the horizon to 366 days. Include overnight carry-in from the previous
    day and clip at both horizon boundaries. Reject overlaps; touching is valid.
    Planning-start and deadline clipping remain the scheduler's responsibility.
    """
    if type(start_date) is not date or type(end_date) is not date:
        raise TypeError("Planning horizon boundaries must be dates")
    days = (end_date - start_date).days + 1
    if not 1 <= days <= 366:
        raise ValueError("Planning horizon must end on/after its start and cover at most 366 days")
    horizon_start = localize_datetime(datetime.combine(start_date, time.min), zone)
    horizon_end = localize_datetime(datetime.combine(end_date + timedelta(days=1), time.min), zone)
    lower = horizon_start.astimezone(timezone.utc)
    upper = horizon_end.astimezone(timezone.utc)
    periods: list[AvailabilityPeriod] = []
    for offset in range(-1, days):
        day = start_date + timedelta(days=offset)
        for rule in rules:
            if rule.weekday != day.weekday():
                continue
            local_start = datetime.combine(day, rule.start_time)
            next_day = day + timedelta(days=1) if rule.end_time < rule.start_time else day
            local_end = datetime.combine(next_day, rule.end_time)
            if local_end <= horizon_start.replace(tzinfo=None):
                continue
            start = max(localize_datetime(local_start, zone).astimezone(timezone.utc), lower)
            end = min(localize_datetime(local_end, zone).astimezone(timezone.utc), upper)
            if start < end:
                periods.append(AvailabilityPeriod(start.astimezone(zone), end.astimezone(zone)))
    periods.sort(key=lambda period: period.start_at.astimezone(timezone.utc))
    for previous, current in zip(periods, periods[1:]):
        if current.start_at.astimezone(timezone.utc) < previous.end_at.astimezone(timezone.utc):
            raise ValueError("Weekly availability windows overlap; adjust the affected days")
    return periods
