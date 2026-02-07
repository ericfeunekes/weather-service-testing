import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from wxbench.domain.mappers.weatherkit import (
    map_weatherkit_alerts,
    map_weatherkit_daily_forecast,
    map_weatherkit_hourly_forecast,
    map_weatherkit_next_hour_forecast,
    map_weatherkit_observation,
)


FIXTURES = Path(__file__).parent.parent / "fixtures"


def load_fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text())


def test_weatherkit_observation_mapping_normalizes_fields():
    payload = load_fixture("weatherkit_payload.json")

    observation = map_weatherkit_observation(payload)

    assert observation.provider == "weatherkit"
    assert observation.location.latitude == pytest.approx(10.0)
    assert observation.location.longitude == pytest.approx(20.0)
    assert observation.observed_at == datetime(2025, 12, 31, 12, tzinfo=timezone.utc)
    assert observation.temperature_c == pytest.approx(5.5)
    assert observation.temperature_apparent_c == pytest.approx(3.0)
    assert observation.dewpoint_c == pytest.approx(1.0)
    assert observation.relative_humidity == pytest.approx(50.0)
    assert observation.cloud_cover_pct == pytest.approx(25.0)
    assert observation.pressure_kpa == pytest.approx(101.3)
    assert observation.visibility_km == pytest.approx(10.0)
    assert observation.wind_speed_kph == pytest.approx(12.0)
    assert observation.wind_direction_deg == 180
    assert observation.wind_gust_kph == pytest.approx(20.0)
    assert observation.precipitation_rate_rain_mm_hr == pytest.approx(0.6)
    assert observation.uv_index == pytest.approx(4.0)
    assert observation.condition == "Clear"


def test_weatherkit_hourly_forecast_mapping_normalizes_fields():
    payload = load_fixture("weatherkit_payload.json")

    periods = map_weatherkit_hourly_forecast(payload)

    assert len(periods) == 1
    period = periods[0]
    assert period.start_time == datetime(2025, 12, 31, 12, tzinfo=timezone.utc)
    assert period.end_time == datetime(2025, 12, 31, 13, tzinfo=timezone.utc)
    assert period.temperature_c == pytest.approx(6.0)
    assert period.temperature_apparent_c == pytest.approx(4.0)
    assert period.dewpoint_c == pytest.approx(0.5)
    assert period.precipitation_probability == pytest.approx(20.0)
    assert period.precipitation_mm == pytest.approx(0.5)
    assert period.precipitation_rate_snow_mm_hr == pytest.approx(0.0)
    assert period.relative_humidity == pytest.approx(40.0)
    assert period.pressure_sea_level_kpa == pytest.approx(101.0)
    assert period.visibility_km == pytest.approx(8.0)
    assert period.cloud_cover_pct == pytest.approx(10.0)
    assert period.wind_speed_kph == pytest.approx(10.0)
    assert period.wind_direction_deg == 190
    assert period.wind_gust_kph == pytest.approx(18.0)
    assert period.uv_index == pytest.approx(3.0)
    assert period.summary == "Clear"


def test_weatherkit_daily_forecast_mapping_normalizes_fields():
    payload = load_fixture("weatherkit_payload.json")

    periods = map_weatherkit_daily_forecast(payload)

    assert len(periods) == 1
    period = periods[0]
    assert period.start_time == datetime(2025, 12, 31, 0, tzinfo=timezone.utc)
    assert period.end_time == datetime(2026, 1, 1, 0, tzinfo=timezone.utc)
    assert period.temperature_c == pytest.approx(5.0)
    assert period.temperature_high_c == pytest.approx(8.0)
    assert period.temperature_low_c == pytest.approx(2.0)
    assert period.precipitation_probability == pytest.approx(30.0)
    assert period.precipitation_type == "rain"
    assert period.precipitation_mm == pytest.approx(2.0)
    assert period.precipitation_amount_snow_mm == pytest.approx(1.2)
    assert period.relative_humidity == pytest.approx(70.0)
    assert period.cloud_cover_pct == pytest.approx(60.0)
    assert period.wind_speed_kph == pytest.approx(14.0)
    assert period.wind_gust_kph is None
    assert period.wind_direction_deg == 200
    assert period.uv_index == pytest.approx(5.0)
    assert period.summary == "Cloudy"


def test_weatherkit_next_hour_forecast_mapping_normalizes_fields():
    payload = load_fixture("weatherkit_payload.json")

    periods = map_weatherkit_next_hour_forecast(payload)

    assert len(periods) == 2
    first = periods[0]
    assert first.start_time == datetime(2025, 12, 31, 12, tzinfo=timezone.utc)
    assert first.end_time == datetime(2025, 12, 31, 12, 1, tzinfo=timezone.utc)
    assert first.precipitation_probability == pytest.approx(60.0)
    assert first.precipitation_rate_rain_mm_hr == pytest.approx(1.2)
    assert first.summary == "rain"

    second = periods[1]
    assert second.start_time == datetime(2025, 12, 31, 12, 1, tzinfo=timezone.utc)
    assert second.end_time == datetime(2025, 12, 31, 12, 2, tzinfo=timezone.utc)
    assert second.precipitation_probability == pytest.approx(50.0)
    assert second.precipitation_rate_rain_mm_hr == pytest.approx(0.8)
    assert second.summary == "rain"


def test_weatherkit_alert_mapping_normalizes_fields():
    payload = load_fixture("weatherkit_payload.json")

    alerts = map_weatherkit_alerts(payload)

    assert len(alerts) == 1
    alert = alerts[0]
    assert alert.alert_id == "9f2c0ea1-4a8c-4f00-9c1f-3a4cfe1a2c90"
    assert alert.area_id == "NSZ001"
    assert alert.area_name == "Example County"
    assert alert.country_code == "CA"
    assert alert.severity == "moderate"
    assert alert.certainty == "likely"
    assert alert.urgency == "expected"
    assert alert.source == "Environment Canada"
    assert alert.description == "Heavy rainfall expected."
    assert alert.responses == ("prepare", "avoid")
    assert alert.issued_at == datetime(2025, 12, 31, 11, 30, tzinfo=timezone.utc)
    assert alert.effective_time == datetime(2025, 12, 31, 12, tzinfo=timezone.utc)
    assert alert.event_start == datetime(2025, 12, 31, 13, tzinfo=timezone.utc)
    assert alert.event_end == datetime(2025, 12, 31, 18, tzinfo=timezone.utc)
    assert alert.expire_time == datetime(2025, 12, 31, 20, tzinfo=timezone.utc)
