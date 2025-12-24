import json
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

import pytest

from wxbench.domain.mappers.msc_geomet import map_msc_geomet_forecast, map_msc_geomet_observation

FIXTURES = Path(__file__).parent.parent / "fixtures"


def load_fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text())


def test_observation_mapping_normalizes_fields():
    raw = load_fixture("msc_geomet_observation.json")

    observation = map_msc_geomet_observation(raw)

    assert observation.provider == "msc_geomet"
    assert observation.station == "CARO"
    assert observation.location.latitude == 45.4
    assert observation.location.longitude == -75.7
    assert observation.observed_at == datetime(2024, 5, 1, 12, tzinfo=timezone.utc)
    assert observation.temperature_c == pytest.approx(12.3)
    assert observation.dewpoint_c == pytest.approx(3.4)
    assert observation.wind_speed_kph == pytest.approx(15.2)
    assert observation.wind_direction_deg == 260
    assert observation.pressure_kpa == pytest.approx(101.2)
    assert observation.relative_humidity == 72
    assert observation.visibility_km == pytest.approx(24.0)
    assert observation.condition == "Rain"
    assert observation.precipitation_last_hour_mm == pytest.approx(0.2)


def test_observation_requires_coordinates():
    raw = load_fixture("msc_geomet_observation.json")
    raw_no_coords = deepcopy(raw)
    raw_no_coords["geometry"]["coordinates"] = []

    with pytest.raises(ValueError):
        map_msc_geomet_observation(raw_no_coords)


def test_forecast_mapping_normalizes_periods():
    raw = load_fixture("msc_geomet_forecast.json")

    periods = map_msc_geomet_forecast(raw)

    assert len(periods) == 2
    first, second = periods

    assert first.issued_at == datetime(2024, 5, 1, 0, tzinfo=timezone.utc)
    assert first.start_time == datetime(2024, 5, 1, 1, tzinfo=timezone.utc)
    assert first.end_time == datetime(2024, 5, 1, 2, tzinfo=timezone.utc)
    assert first.temperature_c == pytest.approx(11.0)
    assert first.precipitation_probability == pytest.approx(20)
    assert first.precipitation_mm == pytest.approx(0.0)
    assert first.summary == "Cloudy"
    assert first.wind_direction_deg == 250
    assert first.wind_speed_kph == pytest.approx(10.5)

    assert second.start_time == datetime(2024, 5, 1, 2, tzinfo=timezone.utc)
    assert second.precipitation_probability == pytest.approx(60)
    assert second.precipitation_mm == pytest.approx(0.8)


def test_forecast_period_requires_start_time():
    raw = load_fixture("msc_geomet_forecast.json")
    broken = deepcopy(raw)
    broken["properties"]["periods"][0].pop("start")

    with pytest.raises(ValueError):
        map_msc_geomet_forecast(broken)
