"""Weekly rules expand into dated windows before reaching the scheduler."""

from datetime import date, datetime, time, timezone
from zoneinfo import ZoneInfo

import pytest

from workload_planner.availability import (
    WeeklyAvailability, expand_weekly_availability, localize_datetime,
)

ZONE = ZoneInfo("America/Los_Angeles")


def test_expands_matching_weekdays_with_inclusive_end_date() -> None:
    rules = [WeeklyAvailability(0, time(18), time(20))]
    periods = expand_weekly_availability(rules, date(2026, 10, 12), date(2026, 10, 19), ZONE)
    assert [period.start_at.day for period in periods] == [12, 19]
    assert all(period.duration_minutes == 120 for period in periods)
    assert all(period.start_at.tzinfo == ZONE for period in periods)


def test_overnight_rule_includes_carry_in_and_clips_at_horizon_end() -> None:
    rules = [WeeklyAvailability(6, time(23), time(2)),  # Sunday into Monday.
             WeeklyAvailability(0, time(23), time(2))]
    periods = expand_weekly_availability(rules, date(2026, 10, 12), date(2026, 10, 12), ZONE)
    assert [(p.start_at.hour, p.end_at.hour, p.duration_minutes) for p in periods] == [
        (0, 2, 120), (23, 0, 60),
    ]
    assert periods[-1].end_at.date() == date(2026, 10, 13)


def test_rejects_weekly_overlaps_and_allows_touching_windows() -> None:
    first = WeeklyAvailability(0, time(18), time(20))
    with pytest.raises(ValueError, match="overlap"):
        expand_weekly_availability([first, first], date(2026, 10, 12), date(2026, 10, 12), ZONE)
    periods = expand_weekly_availability(
        [first, WeeklyAvailability(0, time(20), time(21))],
        date(2026, 10, 12), date(2026, 10, 12), ZONE,
    )
    assert len(periods) == 2


def test_overnight_overlap_with_following_day_is_rejected() -> None:
    with pytest.raises(ValueError, match="overlap"):
        expand_weekly_availability(
            [WeeklyAvailability(0, time(23), time(2)), WeeklyAvailability(1, time(1), time(3))],
            date(2026, 10, 12), date(2026, 10, 13), ZONE,
        )


@pytest.mark.parametrize("weekday,error", [(-1, ValueError), (7, ValueError), (True, TypeError), (1.0, TypeError)])
def test_weekday_must_be_an_integer_from_zero_to_six(weekday, error) -> None:
    with pytest.raises(error, match="weekday"):
        WeeklyAvailability(weekday, time(18), time(20))


@pytest.mark.parametrize("start,end,error", [
    (time(18), time(18), ValueError),
    ("18:00", time(20), TypeError),
    (time(18, tzinfo=timezone.utc), time(20), ValueError),
    (time(18, 0, 1), time(20), ValueError),
])
def test_weekly_times_are_distinct_naive_whole_minutes(start, end, error) -> None:
    with pytest.raises(error):
        WeeklyAvailability(0, start, end)


@pytest.mark.parametrize("start,end", [
    (date(2026, 10, 20), date(2026, 10, 10)),
    (date(2026, 1, 1), date(2027, 1, 2)),
])
def test_rejects_invalid_or_excessive_horizon(start, end) -> None:
    with pytest.raises(ValueError, match="horizon"):
        expand_weekly_availability([], start, end, ZONE)


@pytest.mark.parametrize("local", [datetime(2026, 3, 8, 2, 30), datetime(2026, 11, 1, 1, 30)])
def test_rejects_nonexistent_and_ambiguous_clock_change_times(local) -> None:
    with pytest.raises(ValueError, match="clock change"):
        localize_datetime(local, ZONE)


def test_weekly_expansion_rejects_ambiguous_endpoint() -> None:
    with pytest.raises(ValueError, match="clock change"):
        expand_weekly_availability(
            [WeeklyAvailability(6, time(1, 30), time(3))],
            date(2026, 11, 1), date(2026, 11, 1), ZONE,
        )


def test_valid_endpoints_across_clock_change_use_actual_elapsed_time() -> None:
    periods = expand_weekly_availability(
        [WeeklyAvailability(6, time(0, 30), time(3, 30))],
        date(2026, 11, 1), date(2026, 11, 1), ZONE,
    )
    assert periods[0].duration_minutes == 240


def test_empty_rules_and_nonmatching_weekdays_return_no_periods() -> None:
    for rules in ([], [WeeklyAvailability(1, time(18), time(20))]):
        assert expand_weekly_availability(rules, date(2026, 10, 12), date(2026, 10, 12), ZONE) == []


def test_expansion_is_repeatable_and_does_not_change_rules() -> None:
    rules = [WeeklyAvailability(2, time(18), time(20)), WeeklyAvailability(0, time(18), time(20))]
    original = rules.copy()
    args = (rules, date(2026, 10, 12), date(2026, 10, 19), ZONE)
    assert expand_weekly_availability(*args) == expand_weekly_availability(*args)
    assert rules == original
