from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from math import atan2, cos, radians, sin, sqrt


@dataclass(frozen=True)
class RouteSample:
    latitude: float
    longitude: float
    distance_km: float
    sample_time: datetime


def decode_polyline(encoded: str) -> list[tuple[float, float]]:
    if not encoded:
        return []
    points: list[tuple[float, float]] = []
    index = 0
    lat = 0
    lon = 0
    length = len(encoded)

    while index < length:
        result = 0
        shift = 0
        while True:
            b = ord(encoded[index]) - 63
            index += 1
            result |= (b & 0x1F) << shift
            shift += 5
            if b < 0x20:
                break
        dlat = ~(result >> 1) if result & 1 else (result >> 1)
        lat += dlat

        result = 0
        shift = 0
        while True:
            b = ord(encoded[index]) - 63
            index += 1
            result |= (b & 0x1F) << shift
            shift += 5
            if b < 0x20:
                break
        dlon = ~(result >> 1) if result & 1 else (result >> 1)
        lon += dlon

        points.append((lat / 1e5, lon / 1e5))

    return points


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius_km = 6371.0
    phi1 = radians(lat1)
    phi2 = radians(lat2)
    dphi = radians(lat2 - lat1)
    dlambda = radians(lon2 - lon1)
    a = sin(dphi / 2) ** 2 + cos(phi1) * cos(phi2) * sin(dlambda / 2) ** 2
    return 2 * radius_km * atan2(sqrt(a), sqrt(1 - a))


def _cumulative_distances(points: list[tuple[float, float]]) -> list[float]:
    cumulative = [0.0]
    for idx in range(1, len(points)):
        lat1, lon1 = points[idx - 1]
        lat2, lon2 = points[idx]
        cumulative.append(cumulative[-1] + haversine_km(lat1, lon1, lat2, lon2))
    return cumulative


def _target_distances(
    total_distance_km: float, *, distance_km: float, time_cap_minutes: float, duration_seconds: float
) -> list[float]:
    if total_distance_km <= 0:
        raise ValueError("Route distance must be positive")
    if duration_seconds <= 0:
        raise ValueError("Route duration must be positive")
    if distance_km <= 0:
        raise ValueError("Sampling distance must be positive")
    if time_cap_minutes <= 0:
        raise ValueError("Sampling time cap must be positive")

    distances = {0.0, total_distance_km}

    cursor = distance_km
    while cursor < total_distance_km:
        distances.add(cursor)
        cursor += distance_km

    time_cap_seconds = time_cap_minutes * 60.0
    time_cursor = time_cap_seconds
    while time_cursor < duration_seconds:
        fraction = time_cursor / duration_seconds
        distances.add(total_distance_km * fraction)
        time_cursor += time_cap_seconds

    return sorted(distances)


def sample_route_points(
    geometry: list[tuple[float, float]],
    *,
    total_distance_km: float,
    duration_seconds: float,
    distance_km: float,
    time_cap_minutes: float,
    depart_time: datetime,
) -> list[RouteSample]:
    if not geometry:
        return []
    cumulative = _cumulative_distances(geometry)
    targets = _target_distances(
        total_distance_km,
        distance_km=distance_km,
        time_cap_minutes=time_cap_minutes,
        duration_seconds=duration_seconds,
    )

    samples: list[RouteSample] = []
    for target_km in targets:
        target_km = min(target_km, total_distance_km)
        segment_idx = next(
            (i for i, value in enumerate(cumulative) if value >= target_km),
            len(cumulative) - 1,
        )
        if segment_idx == 0:
            lat, lon = geometry[0]
        else:
            prev_dist = cumulative[segment_idx - 1]
            next_dist = cumulative[segment_idx]
            lat1, lon1 = geometry[segment_idx - 1]
            lat2, lon2 = geometry[segment_idx]
            if next_dist == prev_dist:
                lat, lon = lat2, lon2
            else:
                ratio = (target_km - prev_dist) / (next_dist - prev_dist)
                lat = lat1 + (lat2 - lat1) * ratio
                lon = lon1 + (lon2 - lon1) * ratio

        fraction = target_km / total_distance_km
        sample_time = depart_time + timedelta(seconds=duration_seconds * fraction)
        samples.append(RouteSample(lat, lon, target_km, sample_time))

    return samples
