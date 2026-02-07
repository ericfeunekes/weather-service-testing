from datetime import datetime, timezone

import pytest

from wxbench.domain.mappers.ecowitt import map_ecowitt_realtime
from wxbench.domain.models import Location


def test_ecowitt_realtime_mapping_normalizes_fields() -> None:
    payload = {
        "code": 0,
        "msg": "success",
        "time": "2026-01-05 12:00:00",
        "data": {
            "outdoor": {
                "temperature": {"value": "68.0", "unit": "°F"},
                "humidity": {"value": "50", "unit": "%"},
            },
            "wind": {
                "wind_speed": {"value": "10.0", "unit": "mph"},
                "wind_gust": {"value": "12.0", "unit": "mph"},
                "wind_direction": {"value": "180", "unit": "°"},
            },
            "pressure": {
                "relative": {"value": "1013.2", "unit": "hPa"},
                "absolute": {"value": "1007.1", "unit": "hPa"},
            },
            "rainfall": {
                "hourly": {"value": "0.1", "unit": "in"},
                "daily": {"value": "1.0", "unit": "mm"},
                "weekly": {"value": "0.5", "unit": "in"},
                "monthly": {"value": "10", "unit": "mm"},
                "yearly": {"value": "1.5", "unit": "in"},
                "event": {"value": "0.2", "unit": "in"},
            },
            "solar_and_uvi": {
                "solar": {"value": "123", "unit": "W/m²"},
                "uvi": {"value": "4", "unit": ""},
            },
        },
    }

    observation = map_ecowitt_realtime(
        payload,
        location=Location(latitude=44.639, longitude=-63.587),
        station="Lake house",
        provider="ecowitt",
        capture_time_utc=datetime(2026, 1, 5, 12, 5, tzinfo=timezone.utc),
    )

    assert observation.provider == "ecowitt"
    assert observation.station == "Lake house"
    assert observation.location.latitude == pytest.approx(44.639)
    assert observation.location.longitude == pytest.approx(-63.587)
    assert observation.observed_at == datetime(2026, 1, 5, 12, tzinfo=timezone.utc)
    assert observation.temperature_c == pytest.approx(20.0, abs=0.02)
    assert observation.relative_humidity == pytest.approx(50.0)
    assert observation.wind_speed_kph == pytest.approx(16.0934, abs=0.01)
    assert observation.wind_gust_kph == pytest.approx(19.3121, abs=0.01)
    assert observation.wind_direction_deg == 180
    assert observation.pressure_kpa == pytest.approx(101.32, abs=0.02)
    assert observation.pressure_absolute_kpa == pytest.approx(100.71, abs=0.02)
    assert observation.precipitation_last_hour_mm == pytest.approx(2.54, abs=0.01)
    assert observation.precipitation_daily_mm == pytest.approx(1.0, abs=0.01)
    assert observation.precipitation_weekly_mm == pytest.approx(12.7, abs=0.02)
    assert observation.precipitation_monthly_mm == pytest.approx(10.0, abs=0.01)
    assert observation.precipitation_yearly_mm == pytest.approx(38.1, abs=0.05)
    assert observation.precipitation_event_mm == pytest.approx(5.08, abs=0.02)
    assert observation.uv_index == pytest.approx(4.0)
    assert observation.solar_radiation_wm2 == pytest.approx(123.0)


def test_ecowitt_realtime_mapping_falls_back_to_capture_time() -> None:
    payload = {
        "code": 0,
        "msg": "success",
        "time": "not-a-time",
        "data": {"outdoor": {"temperature": {"value": "10", "unit": "°C"}}},
    }
    capture_time = datetime(2026, 1, 5, 12, 5, tzinfo=timezone.utc)
    observation = map_ecowitt_realtime(
        payload,
        location=Location(latitude=44.639, longitude=-63.587),
        station="Lake house",
        provider="ecowitt",
        capture_time_utc=capture_time,
    )
    assert observation.observed_at == capture_time


def test_ecowitt_realtime_requires_temperature() -> None:
    payload = {"data": {"outdoor": {"humidity": {"value": "50", "unit": "%"}}}}
    with pytest.raises(ValueError):
        map_ecowitt_realtime(payload, location=Location(latitude=0.0, longitude=0.0), station=None)

