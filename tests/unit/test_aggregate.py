"""Tests for daily aggregation from forecast periods."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from wxbench.domain.aggregate import aggregate_daily_from_periods
from wxbench.domain.models import ForecastPeriod, Location


def _make_period(
    *,
    start_time: datetime,
    temperature_c: float | None = None,
    precipitation_mm: float | None = None,
    wind_speed_kph: float | None = None,
    precipitation_probability: float | None = None,
) -> ForecastPeriod:
    return ForecastPeriod(
        provider="test",
        location=Location(latitude=45.0, longitude=-75.0),
        issued_at=datetime(2025, 6, 1, 0, tzinfo=timezone.utc),
        start_time=start_time,
        end_time=start_time + timedelta(hours=1),
        temperature_c=temperature_c,
        precipitation_mm=precipitation_mm,
        wind_speed_kph=wind_speed_kph,
        precipitation_probability=precipitation_probability,
    )


def test_basic_daily_aggregation():
    """Min/max/sum/mean aggregation works for a single day."""
    base = datetime(2025, 6, 15, 0, tzinfo=timezone.utc)
    periods = [
        _make_period(start_time=base + timedelta(hours=h), temperature_c=10.0 + h, precipitation_mm=0.5, wind_speed_kph=20.0 + h)
        for h in range(24)
    ]

    daily = aggregate_daily_from_periods(periods, tz_name="UTC")

    assert len(daily) == 1
    day = daily[0]
    assert day.temperature_high_c == pytest.approx(33.0)  # 10.0 + 23
    assert day.temperature_low_c == pytest.approx(10.0)
    assert day.temperature_c == pytest.approx(21.5)  # mean of 10..33
    assert day.precipitation_mm == pytest.approx(12.0)  # 24 * 0.5
    assert day.wind_speed_kph == pytest.approx(31.5)  # mean of 20..43


def test_daily_aggregation_dst_spring_forward():
    """Spring-forward day (23 hours) should produce correct window."""
    # America/New_York springs forward on 2025-03-09
    tz_name = "America/New_York"
    # Create 23 hourly periods for the local day of 2025-03-09 in UTC
    # EST = UTC-5, EDT = UTC-4
    # Local midnight 2025-03-09 = 2025-03-09 05:00 UTC
    # Local midnight 2025-03-10 = 2025-03-10 04:00 UTC (EDT)
    # That's 23 hours in UTC
    base_utc = datetime(2025, 3, 9, 5, 0, tzinfo=timezone.utc)
    periods = [
        _make_period(start_time=base_utc + timedelta(hours=h), temperature_c=5.0 + h)
        for h in range(23)
    ]

    daily = aggregate_daily_from_periods(periods, tz_name=tz_name)

    assert len(daily) == 1
    day = daily[0]
    # start_time should be midnight local = 05:00 UTC
    assert day.start_time == datetime(2025, 3, 9, 5, 0, tzinfo=timezone.utc)
    # end_time should be next midnight local = 04:00 UTC (23 hours later, not 24)
    assert day.end_time == datetime(2025, 3, 10, 4, 0, tzinfo=timezone.utc)
    assert (day.end_time - day.start_time) == timedelta(hours=23)


def test_daily_aggregation_dst_fall_back():
    """Fall-back day (25 hours) should produce correct window."""
    # America/New_York falls back on 2025-11-02
    tz_name = "America/New_York"
    # EDT = UTC-4, EST = UTC-5
    # Local midnight 2025-11-02 = 2025-11-02 04:00 UTC (EDT)
    # Local midnight 2025-11-03 = 2025-11-03 05:00 UTC (EST)
    # That's 25 hours in UTC
    base_utc = datetime(2025, 11, 2, 4, 0, tzinfo=timezone.utc)
    periods = [
        _make_period(start_time=base_utc + timedelta(hours=h), temperature_c=10.0 + h)
        for h in range(25)
    ]

    daily = aggregate_daily_from_periods(periods, tz_name=tz_name)

    assert len(daily) == 1
    day = daily[0]
    # start_time should be midnight local = 04:00 UTC (EDT)
    assert day.start_time == datetime(2025, 11, 2, 4, 0, tzinfo=timezone.utc)
    # end_time should be next midnight local = 05:00 UTC (EST, 25 hours later)
    assert day.end_time == datetime(2025, 11, 3, 5, 0, tzinfo=timezone.utc)
    assert (day.end_time - day.start_time) == timedelta(hours=25)
