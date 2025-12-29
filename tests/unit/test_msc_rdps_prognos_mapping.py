from __future__ import annotations

import pytest

from wxbench.domain.mappers.msc_rdps_prognos import (
    parse_prognos_payload,
    select_nearest_station,
    value_for_station,
)


def test_parse_prognos_payload_extracts_values() -> None:
    payload = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [-75.0, 45.0, 0.0]},
                "properties": {
                    "prognos_station_id": 1,
                    "reference_datetime": "2025-12-28T00:00:00Z",
                    "forecast_datetime": "2025-12-28T05:00:00Z",
                    "forecast_leadtime": "PT005H",
                    "forecast_value": 280.15,
                    "unit": "K",
                },
            },
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [-120.0, 50.0, 0.0]},
                "properties": {
                    "prognos_station_id": 2,
                    "reference_datetime": "2025-12-28T00:00:00Z",
                    "forecast_datetime": "2025-12-28T05:00:00Z",
                    "forecast_leadtime": "PT005H",
                    "forecast_value": 285.15,
                    "unit": "K",
                },
            },
        ],
    }

    values = parse_prognos_payload(payload)

    assert len(values) == 2
    assert values[0].station_id == "1"
    assert values[0].lead_hours == 5
    assert values[0].unit == "K"


def test_select_nearest_station_prefers_closest() -> None:
    payload = {
        "features": [
            {
                "geometry": {"coordinates": [-75.0, 45.0, 0.0]},
                "properties": {
                    "prognos_station_id": "A",
                    "reference_datetime": "2025-12-28T00:00:00Z",
                    "forecast_datetime": "2025-12-28T05:00:00Z",
                    "forecast_leadtime": "PT005H",
                    "forecast_value": 280.15,
                    "unit": "K",
                },
            },
            {
                "geometry": {"coordinates": [-120.0, 50.0, 0.0]},
                "properties": {
                    "prognos_station_id": "B",
                    "reference_datetime": "2025-12-28T00:00:00Z",
                    "forecast_datetime": "2025-12-28T05:00:00Z",
                    "forecast_leadtime": "PT005H",
                    "forecast_value": 285.15,
                    "unit": "K",
                },
            },
        ]
    }

    values = parse_prognos_payload(payload)
    station_id, lat, lon = select_nearest_station(values, 45.1, -75.1)

    assert station_id == "A"
    assert lat == pytest.approx(45.0)
    assert lon == pytest.approx(-75.0)


def test_value_for_station_returns_match() -> None:
    payload = {
        "features": [
            {
                "geometry": {"coordinates": [-75.0, 45.0, 0.0]},
                "properties": {
                    "prognos_station_id": "A",
                    "reference_datetime": "2025-12-28T00:00:00Z",
                    "forecast_datetime": "2025-12-28T05:00:00Z",
                    "forecast_leadtime": "PT005H",
                    "forecast_value": 280.15,
                    "unit": "K",
                },
            }
        ]
    }

    values = parse_prognos_payload(payload)
    entry = value_for_station(values, "A")

    assert entry is not None
    assert entry.station_id == "A"


def test_parse_prognos_payload_rejects_empty() -> None:
    with pytest.raises(ValueError):
        parse_prognos_payload({"features": []})
