import json
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

import pytest

from wxbench.domain.mappers.ambient_weather import map_ambient_weather_observation

FIXTURES = Path(__file__).parent.parent / "fixtures"


def load_fixture(name: str) -> list[dict]:
    return json.loads((FIXTURES / name).read_text())


def test_observation_mapping_normalizes_fields() -> None:
    raw = load_fixture("ambient_weather_devices.json")

    observation = map_ambient_weather_observation(raw, device_mac="00:11:22:33:44:55")

    assert observation.provider == "ambient_weather"
    assert observation.station == "Backyard"
    assert observation.location.latitude == pytest.approx(40.0)
    assert observation.location.longitude == pytest.approx(-75.0)
    assert observation.observed_at == datetime(2023, 6, 1, 0, tzinfo=timezone.utc)
    assert observation.temperature_c == pytest.approx(20.0, abs=0.01)
    assert observation.dewpoint_c == pytest.approx(12.78, abs=0.01)
    assert observation.wind_speed_kph == pytest.approx(8.0467, abs=0.001)
    assert observation.wind_direction_deg == 135
    assert observation.pressure_kpa == pytest.approx(101.325, abs=0.01)
    assert observation.relative_humidity == pytest.approx(70)
    assert observation.precipitation_last_hour_mm == pytest.approx(0.508, abs=0.001)


def test_observation_maps_extended_fields() -> None:
    payload = [
        {
            "macAddress": "ZZ:YY:XX:WW:VV:UU",
            "info": {"name": "Lab", "coords": {"coords": {"lat": 10.0, "lon": 20.0}}},
            "lastData": {
                "dateutc": 1685577600000,
                "tempf": 77.0,
                "feelsLike": 80.0,
                "tempinf": 72.0,
                "feelsLikein": 70.0,
                "dewPoint": 60.0,
                "dewPointin": 55.0,
                "humidity": 50,
                "humidityin": 40,
                "windspeedmph": 10.0,
                "windgustmph": 12.0,
                "maxdailygust": 20.0,
                "winddir": 180,
                "winddir_avg10m": 200,
                "baromrelin": 29.5,
                "baromabsin": 29.0,
                "hourlyrainin": 0.1,
                "dailyrainin": 0.2,
                "weeklyrainin": 1.0,
                "monthlyrainin": 2.0,
                "yearlyrainin": 10.0,
                "eventrainin": 0.3,
                "uv": 5,
                "solarradiation": 400,
                "battin": 1,
                "battout": 0,
            },
        }
    ]

    observation = map_ambient_weather_observation(payload, device_mac="ZZ:YY:XX:WW:VV:UU")

    assert observation.temperature_apparent_c == pytest.approx(26.67, abs=0.02)
    assert observation.temperature_in_c == pytest.approx(22.22, abs=0.02)
    assert observation.temperature_apparent_in_c == pytest.approx(21.11, abs=0.02)
    assert observation.dewpoint_in_c == pytest.approx(12.78, abs=0.02)
    assert observation.wind_gust_kph == pytest.approx(19.31, abs=0.02)
    assert observation.wind_gust_daily_max_kph == pytest.approx(32.19, abs=0.02)
    assert observation.wind_direction_avg_10m_deg == 200
    assert observation.pressure_absolute_kpa == pytest.approx(98.19, abs=0.02)
    assert observation.relative_humidity_in == pytest.approx(40)
    assert observation.precipitation_daily_mm == pytest.approx(5.08, abs=0.01)
    assert observation.precipitation_weekly_mm == pytest.approx(25.4, abs=0.01)
    assert observation.precipitation_monthly_mm == pytest.approx(50.8, abs=0.01)
    assert observation.precipitation_yearly_mm == pytest.approx(254.0, abs=0.1)
    assert observation.precipitation_event_mm == pytest.approx(7.62, abs=0.01)
    assert observation.uv_index == pytest.approx(5)
    assert observation.solar_radiation_wm2 == pytest.approx(400)
    assert observation.battery_in == pytest.approx(1)
    assert observation.battery_out == pytest.approx(0)


def test_observation_requires_device() -> None:
    with pytest.raises(ValueError):
        map_ambient_weather_observation([])


def test_observation_requires_last_data() -> None:
    raw = load_fixture("ambient_weather_devices.json")
    broken = deepcopy(raw)
    broken[0].pop("lastData", None)

    with pytest.raises(ValueError):
        map_ambient_weather_observation(broken)


def test_observation_requires_coordinates() -> None:
    raw = load_fixture("ambient_weather_devices.json")
    broken = deepcopy(raw)
    broken[0]["info"].pop("coords")

    with pytest.raises(ValueError):
        map_ambient_weather_observation(broken)
