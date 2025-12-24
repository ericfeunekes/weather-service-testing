import json
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

import pytest

from wxbench.domain.mappers.ambient_weather import map_ambient_weather_observation

FIXTURES = Path(__file__).parent.parent / "fixtures"


def load_fixture(name: str) -> list[dict]:
    return json.loads((FIXTURES / name).read_text())


def test_observation_mapping_normalizes_fields(monkeypatch: pytest.MonkeyPatch) -> None:
    raw = load_fixture("ambient_weather_devices.json")
    monkeypatch.delenv("WX_AMBIENT_DEVICE_MAC", raising=False)

    observation = map_ambient_weather_observation(raw)

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
