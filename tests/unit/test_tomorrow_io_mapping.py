import json
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

import pytest

from wxbench.domain.mappers.tomorrow_io import map_tomorrow_io_forecast, map_tomorrow_io_observation

FIXTURES = Path(__file__).parent.parent / "fixtures"


def load_fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text())


def test_observation_mapping_normalizes_fields():
    raw = load_fixture("tomorrow_io_observation.json")

    observation = map_tomorrow_io_observation(raw)

    assert observation.provider == "tomorrow_io"
    assert observation.station == "NYC"
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


def test_observation_requires_coordinates():
    raw = load_fixture("tomorrow_io_observation.json")
    broken = deepcopy(raw)
    broken["data"]["location"].pop("lat")

    with pytest.raises(ValueError):
        map_tomorrow_io_observation(broken)


def test_forecast_mapping_normalizes_intervals():
    raw = load_fixture("tomorrow_io_forecast.json")

    periods = map_tomorrow_io_forecast(raw)

    assert len(periods) == 2
    first, second = periods

    assert first.issued_at == datetime(2024, 5, 1, 12, 30, tzinfo=timezone.utc)
    assert first.start_time == datetime(2024, 5, 1, 13, tzinfo=timezone.utc)
    assert first.end_time == datetime(2024, 5, 1, 14, tzinfo=timezone.utc)
    assert first.temperature_c == pytest.approx(16.0)
    assert first.precipitation_probability == pytest.approx(20)
    assert first.precipitation_mm == pytest.approx(0.0)
    assert first.summary == "Cloudy"
    assert first.wind_speed_kph == pytest.approx(21.6)
    assert first.wind_direction_deg == 220

    assert second.start_time == datetime(2024, 5, 1, 14, tzinfo=timezone.utc)
    assert second.end_time == datetime(2024, 5, 1, 15, tzinfo=timezone.utc)
    assert second.precipitation_probability == pytest.approx(55)
    assert second.precipitation_mm == pytest.approx(0.4)
    assert second.summary == "Light Rain"


def test_forecast_requires_start_time():
    raw = load_fixture("tomorrow_io_forecast.json")
    broken = deepcopy(raw)
    broken["data"]["timelines"][0]["intervals"][0].pop("startTime")

    with pytest.raises(ValueError):
        map_tomorrow_io_forecast(broken)
