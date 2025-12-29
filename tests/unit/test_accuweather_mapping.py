import json
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

import pytest

from wxbench.domain.mappers.accuweather import (
    map_accuweather_daily_forecast,
    map_accuweather_hourly_forecast,
    map_accuweather_minute_forecast,
    map_accuweather_observation,
)

FIXTURES = Path(__file__).parent.parent / "fixtures"


def load_fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text())


def test_minute_forecast_mapping_normalizes_intervals():
    raw = load_fixture("accuweather_minute_forecast.json")

    issued_at = datetime(2024, 5, 1, 17, 0, tzinfo=timezone.utc)
    periods = map_accuweather_minute_forecast(raw, latitude=40.7, longitude=-74.0, issued_at=issued_at)

    assert len(periods) == 2
    first, second = periods

    assert first.issued_at == issued_at
    assert first.start_time == datetime(2024, 5, 1, 17, 0, tzinfo=timezone.utc)
    assert first.end_time == datetime(2024, 5, 1, 17, 1, tzinfo=timezone.utc)
    assert first.summary == "Light rain"
    assert first.location.latitude == pytest.approx(40.7)
    assert first.location.longitude == pytest.approx(-74.0)

    assert second.start_time == datetime(2024, 5, 1, 17, 1, tzinfo=timezone.utc)
    assert second.end_time == datetime(2024, 5, 1, 17, 2, tzinfo=timezone.utc)


def test_minute_forecast_requires_intervals():
    raw = load_fixture("accuweather_minute_forecast.json")
    broken = deepcopy(raw)
    broken.pop("Summaries")

    with pytest.raises(ValueError):
        map_accuweather_minute_forecast(
            broken,
            latitude=40.7,
            longitude=-74.0,
            issued_at=datetime(2024, 5, 1, 17, 0, tzinfo=timezone.utc),
        )


def test_minute_forecast_requires_start_time():
    raw = load_fixture("accuweather_minute_forecast.json")
    broken = deepcopy(raw)
    broken["Summaries"][0].pop("StartMinute")

    with pytest.raises(ValueError):
        map_accuweather_minute_forecast(
            broken,
            latitude=40.7,
            longitude=-74.0,
            issued_at=datetime(2024, 5, 1, 17, 0, tzinfo=timezone.utc),
        )


def test_observation_mapping_includes_apparent_gust_uv():
    payload = [
        {
            "EpochTime": 1700000000,
            "WeatherText": "Cloudy",
            "Temperature": {"Metric": {"Value": 5.0, "Unit": "C"}},
            "RealFeelTemperature": {"Metric": {"Value": 2.0, "Unit": "C"}},
            "RealFeelTemperatureShade": {"Metric": {"Value": 1.0, "Unit": "C"}},
            "ApparentTemperature": {"Metric": {"Value": 3.0, "Unit": "C"}},
            "WindChillTemperature": {"Metric": {"Value": -2.0, "Unit": "C"}},
            "WetBulbTemperature": {"Value": 0.5, "Unit": "C"},
            "WetBulbGlobeTemperature": {"Value": 0.0, "Unit": "C"},
            "Past24HourTemperatureDeparture": {"Metric": {"Value": -1.5, "Unit": "C"}},
            "Wind": {"Speed": {"Metric": {"Value": 10.0, "Unit": "km/h"}}, "Direction": {"Degrees": 200}},
            "WindGust": {"Speed": {"Metric": {"Value": 20.0, "Unit": "km/h"}}},
            "UVIndex": 3,
            "IndoorRelativeHumidity": 40,
            "CloudCover": 50,
            "Ceiling": {"Metric": {"Value": 1200.0, "Unit": "m"}},
            "PrecipitationType": "Rain",
            "PressureTendency": {"LocalizedText": "Rising"},
            "WeatherIcon": 7,
        }
    ]

    observation = map_accuweather_observation(payload, latitude=10.0, longitude=20.0)

    assert observation.temperature_apparent_c == pytest.approx(2.0)
    assert observation.wind_gust_kph == pytest.approx(20.0)
    assert observation.uv_index == pytest.approx(3.0)
    assert observation.temperature_apparent_shade_c == pytest.approx(1.0)
    assert observation.temperature_apparent_alt_c == pytest.approx(3.0)
    assert observation.temperature_wind_chill_c == pytest.approx(-2.0)
    assert observation.temperature_wet_bulb_c == pytest.approx(0.5)
    assert observation.temperature_wet_bulb_globe_c == pytest.approx(0.0)
    assert observation.temperature_departure_24h_c == pytest.approx(-1.5)
    assert observation.relative_humidity_in == pytest.approx(40)
    assert observation.cloud_cover_pct == pytest.approx(50)
    assert observation.cloud_ceiling_km == pytest.approx(1.2)
    assert observation.precipitation_type == "Rain"
    assert observation.pressure_tendency == "Rising"
    assert observation.condition_code == 7


def test_hourly_forecast_mapping_includes_apparent_gust_uv():
    payload = [
        {
            "EpochDateTime": 1700000000,
            "Temperature": {"Metric": {"Value": 5.0, "Unit": "C"}},
            "RealFeelTemperature": {"Metric": {"Value": 1.0, "Unit": "C"}},
            "RealFeelTemperatureShade": {"Metric": {"Value": 0.5, "Unit": "C"}},
            "DewPoint": {"Value": -2.0, "Unit": "C"},
            "WetBulbTemperature": {"Value": -1.0, "Unit": "C"},
            "WetBulbGlobeTemperature": {"Value": -0.5, "Unit": "C"},
            "Wind": {"Speed": {"Metric": {"Value": 8.0, "Unit": "km/h"}}, "Direction": {"Degrees": 180}},
            "WindGust": {"Speed": {"Metric": {"Value": 15.0, "Unit": "km/h"}}},
            "UVIndex": 2,
            "RelativeHumidity": 55,
            "Visibility": {"Value": 10.0, "Unit": "km"},
            "Ceiling": {"Value": 3000.0, "Unit": "m"},
            "PrecipitationProbability": 20,
            "ThunderstormProbability": 5,
            "RainProbability": 15,
            "SnowProbability": 0,
            "IceProbability": 0,
            "TotalLiquid": {"Value": 1.2, "Unit": "mm"},
            "Rain": {"Value": 1.0, "Unit": "mm"},
            "Snow": {"Value": 0.2, "Unit": "mm"},
            "WeatherIcon": 12,
        }
    ]

    periods = map_accuweather_hourly_forecast(payload, latitude=10.0, longitude=20.0)

    assert periods[0].temperature_apparent_c == pytest.approx(1.0)
    assert periods[0].wind_gust_kph == pytest.approx(15.0)
    assert periods[0].uv_index == pytest.approx(2.0)
    assert periods[0].temperature_apparent_shade_c == pytest.approx(0.5)
    assert periods[0].dewpoint_c == pytest.approx(-2.0)
    assert periods[0].temperature_wet_bulb_c == pytest.approx(-1.0)
    assert periods[0].temperature_wet_bulb_globe_c == pytest.approx(-0.5)
    assert periods[0].relative_humidity == pytest.approx(55)
    assert periods[0].visibility_km == pytest.approx(10.0)
    assert periods[0].cloud_ceiling_km == pytest.approx(3.0)
    assert periods[0].precipitation_probability == pytest.approx(20)
    assert periods[0].precipitation_probability_thunderstorm == pytest.approx(5)
    assert periods[0].precipitation_probability_rain == pytest.approx(15)
    assert periods[0].precipitation_amount_rain_mm == pytest.approx(1.0)
    assert periods[0].precipitation_amount_snow_mm == pytest.approx(0.2)
    assert periods[0].condition_code == 12


def test_daily_forecast_mapping_includes_apparent_gust_uv():
    payload = {
        "DailyForecasts": [
            {
                "EpochDate": 1700000000,
                "Temperature": {
                    "Minimum": {"Metric": {"Value": 1.0, "Unit": "C"}},
                    "Maximum": {"Metric": {"Value": 6.0, "Unit": "C"}},
                },
                "RealFeelTemperature": {
                    "Minimum": {"Metric": {"Value": -1.0, "Unit": "C"}},
                    "Maximum": {"Metric": {"Value": 2.0, "Unit": "C"}},
                },
                "RealFeelTemperatureShade": {
                    "Minimum": {"Value": -2.0, "Unit": "C"},
                    "Maximum": {"Value": 0.0, "Unit": "C"},
                },
                "Day": {
                    "Wind": {"Speed": {"Metric": {"Value": 12.0, "Unit": "km/h"}}, "Direction": {"Degrees": 210}},
                    "WindGust": {"Speed": {"Metric": {"Value": 18.0, "Unit": "km/h"}}},
                    "UVIndexFloat": {"Minimum": 1.0, "Maximum": 3.0},
                    "CloudCover": 30,
                    "RelativeHumidity": {"Average": 60},
                    "Evapotranspiration": {"Value": 1.5, "Unit": "mm"},
                    "SolarIrradiance": {"Value": 250.0, "Unit": "W/m2"},
                    "WetBulbTemperature": {
                        "Minimum": {"Value": -2.0, "Unit": "C"},
                        "Maximum": {"Value": 1.0, "Unit": "C"},
                        "Average": {"Value": -0.5, "Unit": "C"},
                    },
                    "WetBulbGlobeTemperature": {
                        "Minimum": {"Value": -1.5, "Unit": "C"},
                        "Maximum": {"Value": 1.5, "Unit": "C"},
                        "Average": {"Value": 0.0, "Unit": "C"},
                    },
                    "PrecipitationProbability": 40,
                    "RainProbability": 30,
                    "SnowProbability": 10,
                    "ThunderstormProbability": 5,
                    "Rain": {"Value": 2.0, "Unit": "mm"},
                },
                "HoursOfSun": 5.5,
            }
        ]
    }

    periods = map_accuweather_daily_forecast(payload, latitude=10.0, longitude=20.0)

    assert periods[0].temperature_apparent_c == pytest.approx(0.5)
    assert periods[0].wind_gust_kph == pytest.approx(18.0)
    assert periods[0].uv_index == pytest.approx(2.0)
    assert periods[0].temperature_apparent_shade_c == pytest.approx(-1.0)
    assert periods[0].cloud_cover_pct == pytest.approx(30)
    assert periods[0].relative_humidity == pytest.approx(60)
    assert periods[0].evapotranspiration_mm == pytest.approx(1.5)
    assert periods[0].solar_irradiance_wm2 == pytest.approx(250.0)
    assert periods[0].temperature_wet_bulb_c == pytest.approx(-0.5)
    assert periods[0].temperature_wet_bulb_globe_c == pytest.approx(0.0)
    assert periods[0].precipitation_probability == pytest.approx(40)
    assert periods[0].precipitation_probability_rain == pytest.approx(30)
    assert periods[0].precipitation_amount_rain_mm == pytest.approx(2.0)
    assert periods[0].sun_hours == pytest.approx(5.5)
