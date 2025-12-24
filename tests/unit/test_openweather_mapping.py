import json
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

import pytest

from wxbench.domain.mappers.openweather import map_openweather_forecast, map_openweather_observation

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
    assert observation.precipitation_last_hour_mm == pytest.approx(0.25)


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
