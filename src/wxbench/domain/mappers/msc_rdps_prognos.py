"""Mapping helpers for MSC RDPS PROGNOS station forecasts."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from math import asin, cos, radians, sin, sqrt
from typing import Any, Iterable, Mapping, Optional, Sequence


@dataclass(frozen=True)
class PrognosStationValue:
    station_id: str
    latitude: float
    longitude: float
    reference_time: datetime
    forecast_time: datetime
    lead_hours: int
    unit: str
    value: float


def _default_iso8601_parser(value: str) -> datetime:
    cleaned = value.replace("Z", "+00:00") if value.endswith("Z") else value
    return datetime.fromisoformat(cleaned)


def _parse_iso8601(value: str) -> datetime:
    return _default_iso8601_parser(value)


def _parse_lead_hours(value: str) -> int:
    if not value.startswith("PT") or not value.endswith("H"):
        raise ValueError(f"Unexpected lead time format: {value}")
    return int(value[2:-1])


def _to_optional_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius_km = 6371.0
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    lat1_rad = radians(lat1)
    lat2_rad = radians(lat2)
    a = sin(dlat / 2) ** 2 + cos(lat1_rad) * cos(lat2_rad) * sin(dlon / 2) ** 2
    return 2 * radius_km * asin(sqrt(a))


def parse_prognos_payload(payload: Mapping[str, Any]) -> list[PrognosStationValue]:
    features: Iterable[Any] = payload.get("features") or []
    if not isinstance(features, Iterable):
        raise ValueError("Missing features array in RDPS PROGNOS payload")

    values: list[PrognosStationValue] = []
    for feature in features:
        if not isinstance(feature, Mapping):
            continue
        geometry = feature.get("geometry") or {}
        coords = geometry.get("coordinates") or []
        if not isinstance(coords, Sequence) or len(coords) < 2:
            continue
        longitude, latitude = coords[0], coords[1]
        properties: Mapping[str, Any] = feature.get("properties") or {}
        station_id = properties.get("prognos_station_id")
        reference_time = properties.get("reference_datetime")
        forecast_time = properties.get("forecast_datetime")
        lead_time = properties.get("forecast_leadtime")
        value = properties.get("forecast_value")
        unit = properties.get("unit")

        if station_id is None or reference_time is None or forecast_time is None or lead_time is None:
            continue

        numeric_value = _to_optional_float(value)
        if numeric_value is None or unit is None:
            continue

        values.append(
            PrognosStationValue(
                station_id=str(station_id),
                latitude=float(latitude),
                longitude=float(longitude),
                reference_time=_parse_iso8601(str(reference_time)),
                forecast_time=_parse_iso8601(str(forecast_time)),
                lead_hours=_parse_lead_hours(str(lead_time)),
                unit=str(unit),
                value=float(numeric_value),
            )
        )

    if not values:
        raise ValueError("No usable station values in RDPS PROGNOS payload")

    return values


def select_nearest_station(
    values: Iterable[PrognosStationValue], target_lat: float, target_lon: float
) -> tuple[str, float, float]:
    best: Optional[PrognosStationValue] = None
    best_distance = float("inf")
    for entry in values:
        distance = _haversine_km(target_lat, target_lon, entry.latitude, entry.longitude)
        if distance < best_distance:
            best_distance = distance
            best = entry
    if best is None:
        raise ValueError("Unable to select nearest station from RDPS PROGNOS payload")
    return best.station_id, best.latitude, best.longitude


def value_for_station(
    values: Iterable[PrognosStationValue], station_id: str
) -> Optional[PrognosStationValue]:
    for entry in values:
        if entry.station_id == station_id:
            return entry
    return None


__all__ = [
    "PrognosStationValue",
    "parse_prognos_payload",
    "select_nearest_station",
    "value_for_station",
]
