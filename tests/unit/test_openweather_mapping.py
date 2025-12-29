import json
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

import pytest

from wxbench.domain.mappers.openweather import (
    map_openweather_forecast,
    map_openweather_observation,
    map_openweather_onecall_daily,
    map_openweather_onecall_hourly,
)

FIXTURES = Path(__file__).parent.parent / "fixtures"


def load_fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text())


def test_observation_mapping_normalizes_fields():
    raw = load_fixture("openweather_observation.json")

    observation = map_openweather_observation(raw)

    assert observation.provider == "openweather"
    assert observation.station == "London"
    assert observation.location.latitude == pytest.approx(51.51)
    assert observation.location.longitude == pytest.approx(-0.13)
    assert observation.observed_at == datetime(2023, 5, 1, 0, tzinfo=timezone.utc)
    assert observation.temperature_c == pytest.approx(16.67, abs=0.01)
    assert observation.wind_speed_kph == pytest.approx(14.76, abs=0.01)
    assert observation.wind_direction_deg == 80
    assert observation.pressure_kpa == pytest.approx(101.2)
    assert observation.relative_humidity == pytest.approx(82)
    assert observation.visibility_km == pytest.approx(10.0)
    assert observation.condition == "light rain"
    assert observation.cloud_cover_pct == pytest.approx(90)
    assert observation.condition_code == 500
    assert observation.precipitation_last_hour_mm == pytest.approx(0.25)


def test_observation_mapping_includes_apparent_and_gust():
    payload = {
        "coord": {"lat": 10.0, "lon": 20.0},
        "dt": 1700000000,
        "main": {"temp": 280.0, "feels_like": 275.0, "pressure": 1010, "humidity": 80},
        "wind": {"speed": 5.0, "deg": 180, "gust": 9.0},
        "weather": [{"description": "cloudy"}],
    }

    observation = map_openweather_observation(payload)

    assert observation.temperature_apparent_c == pytest.approx(1.85, abs=0.01)
    assert observation.wind_gust_kph == pytest.approx(32.4, abs=0.01)


def test_observation_requires_coordinates():
    raw = load_fixture("openweather_observation.json")
    broken = deepcopy(raw)
    broken.pop("coord")

    with pytest.raises(ValueError):
        map_openweather_observation(broken)


def test_forecast_mapping_normalizes_entries():
    raw = load_fixture("openweather_forecast.json")

    periods = map_openweather_forecast(raw)

    assert len(periods) == 2
    first, second = periods

    assert first.issued_at == datetime(2023, 5, 1, 3, tzinfo=timezone.utc)
    assert first.start_time == datetime(2023, 5, 1, 3, tzinfo=timezone.utc)
    assert first.end_time == datetime(2023, 5, 1, 6, tzinfo=timezone.utc)
    assert first.temperature_c == pytest.approx(17.0, abs=0.01)
    assert first.temperature_high_c == pytest.approx(18.0, abs=0.01)
    assert first.temperature_low_c == pytest.approx(16.0, abs=0.01)
    assert first.precipitation_probability == pytest.approx(10)
    assert first.precipitation_mm == pytest.approx(0.0)
    assert first.summary == "few clouds"
    assert first.wind_speed_kph == pytest.approx(12.6)
    assert first.wind_direction_deg == 90
    assert first.relative_humidity == pytest.approx(70)
    assert first.pressure_sea_level_kpa == pytest.approx(101.4)

    assert second.start_time == datetime(2023, 5, 1, 6, tzinfo=timezone.utc)
    assert second.precipitation_probability == pytest.approx(60)
    assert second.precipitation_mm == pytest.approx(0.7)
    assert second.summary == "light rain"


def test_forecast_requires_coordinates():
    raw = load_fixture("openweather_forecast.json")
    broken = deepcopy(raw)
    broken["city"].pop("coord")

    with pytest.raises(ValueError):
        map_openweather_forecast(broken)


def test_onecall_hourly_mapping_includes_uv_and_gust():
    payload = {
        "lat": 10.0,
        "lon": 20.0,
        "hourly": [
            {
                "dt": 1700000000,
                "temp": 5.0,
                "feels_like": 2.0,
                "wind_speed": 4.0,
                "wind_deg": 200,
                "wind_gust": 8.0,
                "dew_point": 1.0,
                "humidity": 55,
                "pressure": 1005,
                "clouds": 40,
                "visibility": 9000,
                "weather": [{"id": 800, "description": "clear"}],
                "uvi": 1.2,
            }
        ],
    }

    periods = map_openweather_onecall_hourly(payload)

    assert len(periods) == 1
    assert periods[0].temperature_apparent_c == pytest.approx(2.0)
    assert periods[0].wind_gust_kph == pytest.approx(28.8, abs=0.01)
    assert periods[0].uv_index == pytest.approx(1.2)
    assert periods[0].dewpoint_c == pytest.approx(1.0)
    assert periods[0].relative_humidity == pytest.approx(55)
    assert periods[0].pressure_sea_level_kpa == pytest.approx(100.5)
    assert periods[0].cloud_cover_pct == pytest.approx(40)
    assert periods[0].visibility_km == pytest.approx(9.0)
    assert periods[0].condition_code == 800


def test_onecall_daily_mapping_includes_uv_and_gust():
    payload = {
        "lat": 10.0,
        "lon": 20.0,
        "daily": [
            {
                "dt": 1700000000,
                "temp": {"day": 4.0, "min": 1.0, "max": 6.0},
                "feels_like": {"day": 0.0},
                "wind_speed": 5.0,
                "wind_deg": 250,
                "wind_gust": 10.0,
                "dew_point": 2.0,
                "humidity": 65,
                "pressure": 1012,
                "clouds": 70,
                "weather": [{"id": 601, "description": "snow"}],
                "uvi": 2.4,
            }
        ],
    }

    periods = map_openweather_onecall_daily(payload)

    assert len(periods) == 1
    assert periods[0].temperature_apparent_c == pytest.approx(0.0)
    assert periods[0].wind_gust_kph == pytest.approx(36.0, abs=0.01)
    assert periods[0].uv_index == pytest.approx(2.4)
    assert periods[0].dewpoint_c == pytest.approx(2.0)
    assert periods[0].relative_humidity == pytest.approx(65)
    assert periods[0].pressure_sea_level_kpa == pytest.approx(101.2)
    assert periods[0].cloud_cover_pct == pytest.approx(70)
    assert periods[0].condition_code == 601
