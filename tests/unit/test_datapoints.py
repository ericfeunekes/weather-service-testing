from __future__ import annotations

from datetime import datetime, timezone

from wxbench.domain.datapoints import (
    PRODUCT_FORECAST_DAILY,
    PRODUCT_FORECAST_HOURLY,
    observation_to_datapoints,
    forecast_to_datapoints,
)
from wxbench.domain.models import ForecastPeriod, Location, Observation


def test_observation_to_datapoints_emits_metrics():
    observed_at = datetime(2024, 1, 1, 12, tzinfo=timezone.utc)
    run_at = datetime(2024, 1, 1, 12, 30, tzinfo=timezone.utc)
    observation = Observation(
        provider="demo",
        station="station-a",
        location=Location(latitude=10.0, longitude=20.0),
        observed_at=observed_at,
        temperature_c=21.5,
        relative_humidity=55.0,
        condition="Clear",
    )

    points = observation_to_datapoints(observation, run_at=run_at, tz_name="UTC")

    assert points
    assert all(point.product_kind == "observation" for point in points)
    assert any(point.metric_type == "temperature_air" and point.unit == "C" for point in points)
    assert any(point.metric_type == "humidity" and point.unit == "%" for point in points)
    assert any(point.metric_type == "condition" and point.value_text == "Clear" for point in points)
    assert all(point.lead_unit is None for point in points)


def test_forecast_to_datapoints_hourly_lead_time():
    run_at = datetime(2024, 1, 1, 0, tzinfo=timezone.utc)
    start_time = datetime(2024, 1, 1, 5, tzinfo=timezone.utc)
    end_time = datetime(2024, 1, 1, 6, tzinfo=timezone.utc)
    forecast = ForecastPeriod(
        provider="demo",
        location=Location(latitude=10.0, longitude=20.0),
        issued_at=run_at,
        start_time=start_time,
        end_time=end_time,
        temperature_c=10.0,
        dewpoint_c=5.0,
    )

    points = forecast_to_datapoints(
        forecast,
        run_at=run_at,
        tz_name="UTC",
        product_kind=PRODUCT_FORECAST_HOURLY,
    )

    assert points
    assert all(point.lead_unit == "hour" for point in points)
    assert all(point.lead_offset == 5 for point in points)
    assert all(point.lead_label == "+5h" for point in points)
    assert any(point.metric_type == "dewpoint" for point in points)


def test_forecast_to_datapoints_daily_lead_time():
    run_at = datetime(2024, 1, 1, 10, tzinfo=timezone.utc)
    start_time = datetime(2024, 1, 3, 0, tzinfo=timezone.utc)
    end_time = datetime(2024, 1, 4, 0, tzinfo=timezone.utc)
    forecast = ForecastPeriod(
        provider="demo",
        location=Location(latitude=10.0, longitude=20.0),
        issued_at=run_at,
        start_time=start_time,
        end_time=end_time,
        temperature_high_c=12.0,
    )

    points = forecast_to_datapoints(
        forecast,
        run_at=run_at,
        tz_name="UTC",
        product_kind=PRODUCT_FORECAST_DAILY,
    )

    assert points
    assert all(point.lead_unit == "day" for point in points)
    assert all(point.lead_offset == 2 for point in points)
    assert all(point.lead_label == "+2d" for point in points)
    assert all(point.local_day is not None for point in points)
