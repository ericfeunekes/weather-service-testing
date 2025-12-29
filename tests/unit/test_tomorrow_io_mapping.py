import json
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

import pytest

from wxbench.domain.mappers.tomorrow_io import (
    map_tomorrow_io_daily_forecast,
    map_tomorrow_io_forecast,
    map_tomorrow_io_observation,
)

FIXTURES = Path(__file__).parent.parent / "fixtures"


def load_fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text())


def test_observation_mapping_normalizes_fields():
    raw = load_fixture("tomorrow_io_observation.json")

    observation = map_tomorrow_io_observation(raw)

    assert observation.provider == "tomorrow_io"
    assert observation.station is None
    assert observation.location.latitude == pytest.approx(40.7)
    assert observation.location.longitude == pytest.approx(-74.0)
    assert observation.observed_at == datetime(2024, 5, 1, 12, tzinfo=timezone.utc)
    assert observation.temperature_c == pytest.approx(15.2)
    assert observation.dewpoint_c == pytest.approx(7.5)
    assert observation.wind_speed_kph == pytest.approx(19.8)
    assert observation.wind_direction_deg == 210
    assert observation.pressure_kpa == pytest.approx(101.25)
    assert observation.relative_humidity == pytest.approx(62)
    assert observation.visibility_km == pytest.approx(15.0)
    assert observation.condition == "Light Rain"
    assert observation.precipitation_last_hour_mm == pytest.approx(0.1)
    assert observation.precipitation_rate_rain_mm_hr == pytest.approx(0.1)
    assert observation.pressure_surface_kpa == pytest.approx(101.25)
    assert observation.condition_code == 4200


def test_observation_mapping_includes_apparent_gust_uv():
    payload = {
        "location": {"lat": 10.0, "lon": 20.0},
        "data": {
            "time": "2024-05-01T12:00:00Z",
            "values": {
                "temperature": 10.0,
                "temperatureApparent": 7.0,
                "windSpeed": 5.0,
                "windDirection": 180,
                "windGust": 9.0,
                "uvIndex": 3.2,
                "pressureSeaLevel": 1008.0,
                "cloudCover": 45,
                "weatherCode": 1000,
            },
        },
    }

    observation = map_tomorrow_io_observation(payload)

    assert observation.temperature_apparent_c == pytest.approx(7.0)
    assert observation.wind_gust_kph == pytest.approx(32.4, abs=0.01)
    assert observation.uv_index == pytest.approx(3.2)
    assert observation.pressure_sea_level_kpa == pytest.approx(100.8)
    assert observation.cloud_cover_pct == pytest.approx(45)
    assert observation.condition_code == 1000


def test_observation_requires_coordinates():
    raw = load_fixture("tomorrow_io_observation.json")
    broken = deepcopy(raw)
    broken["location"].pop("lat")

    with pytest.raises(ValueError):
        map_tomorrow_io_observation(broken)


def test_forecast_mapping_normalizes_intervals():
    raw = load_fixture("tomorrow_io_forecast.json")

    periods = map_tomorrow_io_forecast(raw)

    assert len(periods) == 2
    first, second = periods

    assert first.issued_at == datetime(2024, 5, 1, 13, tzinfo=timezone.utc)
    assert first.start_time == datetime(2024, 5, 1, 13, tzinfo=timezone.utc)
    assert first.end_time == datetime(2024, 5, 1, 14, tzinfo=timezone.utc)
    assert first.temperature_c == pytest.approx(16.0)
    assert first.precipitation_probability == pytest.approx(20)
    assert first.precipitation_mm == pytest.approx(0.0)
    assert first.summary == "Cloudy"
    assert first.condition_code == 1001
    assert first.wind_speed_kph == pytest.approx(21.6)
    assert first.wind_direction_deg == 220

    assert second.start_time == datetime(2024, 5, 1, 14, tzinfo=timezone.utc)
    assert second.end_time == datetime(2024, 5, 1, 15, tzinfo=timezone.utc)
    assert second.precipitation_probability == pytest.approx(55)
    assert second.precipitation_mm == pytest.approx(0.4)
    assert second.summary == "Light Rain"
    assert second.condition_code == 4200


def test_forecast_requires_start_time():
    raw = load_fixture("tomorrow_io_forecast.json")
    broken = deepcopy(raw)
    broken["timelines"]["hourly"][0].pop("time")

    with pytest.raises(ValueError):
        map_tomorrow_io_forecast(broken)


def test_forecast_mapping_includes_apparent_gust_uv():
    payload = {
        "location": {"lat": 10.0, "lon": 20.0},
        "timelines": {
            "hourly": [
                {
                    "time": "2024-05-01T13:00:00Z",
                    "values": {
                        "temperature": 8.0,
                        "temperatureApparent": 5.0,
                        "windSpeed": 4.0,
                        "windDirection": 200,
                        "windGust": 8.0,
                        "uvIndex": 2.2,
                        "humidity": 55,
                        "pressureSeaLevel": 1007.0,
                        "cloudCover": 30,
                        "weatherCode": 1100,
                    },
                }
            ]
        },
    }

    periods = map_tomorrow_io_forecast(payload)

    assert periods[0].temperature_apparent_c == pytest.approx(5.0)
    assert periods[0].wind_gust_kph == pytest.approx(28.8, abs=0.01)
    assert periods[0].uv_index == pytest.approx(2.2)
    assert periods[0].relative_humidity == pytest.approx(55)
    assert periods[0].pressure_sea_level_kpa == pytest.approx(100.7)
    assert periods[0].cloud_cover_pct == pytest.approx(30)
    assert periods[0].condition_code == 1100


def test_daily_forecast_mapping_includes_apparent_gust_uv():
    payload = {
        "location": {"lat": 10.0, "lon": 20.0},
        "timelines": {
            "daily": [
                {
                    "time": "2024-05-01T00:00:00Z",
                    "values": {
                        "temperatureAvg": 6.0,
                        "temperatureApparentAvg": 3.0,
                        "temperatureMax": 9.0,
                        "temperatureMin": 2.0,
                        "windSpeedAvg": 4.0,
                        "windDirectionAvg": 210,
                        "windGustAvg": 9.0,
                        "uvIndexMax": 5.0,
                        "humidityAvg": 60,
                        "precipitationProbabilityMax": 70,
                        "rainAccumulationSum": 2.5,
                    },
                }
            ]
        },
    }

    periods = map_tomorrow_io_daily_forecast(payload)

    assert periods[0].temperature_apparent_c == pytest.approx(3.0)
    assert periods[0].wind_gust_kph == pytest.approx(32.4, abs=0.01)
    assert periods[0].uv_index == pytest.approx(5.0)
    assert periods[0].relative_humidity == pytest.approx(60)
    assert periods[0].precipitation_probability == pytest.approx(70)
    assert periods[0].precipitation_amount_rain_mm == pytest.approx(2.5)
