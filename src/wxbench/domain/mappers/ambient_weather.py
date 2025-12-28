"""Mapping helpers for AmbientWeather payloads."""
from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any, Mapping, MutableMapping, Optional, Sequence

from wxbench.domain.models import Location, Observation


INHG_TO_KPA = 3.386389
MPH_TO_KPH = 1.60934
INCH_TO_MM = 25.4


def _to_optional_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _to_optional_int(value: Any) -> Optional[int]:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _f_to_c(value: Optional[float]) -> Optional[float]:
    if value is None:
        return None
    return (value - 32.0) * 5.0 / 9.0


def _mph_to_kph(value: Optional[float]) -> Optional[float]:
    if value is None:
        return None
    return value * MPH_TO_KPH


def _inHg_to_kpa(value: Optional[float]) -> Optional[float]:
    if value is None:
        return None
    return value * INHG_TO_KPA


def _inches_to_mm(value: Optional[float]) -> Optional[float]:
    if value is None:
        return None
    return value * INCH_TO_MM


def _parse_observed_at(timestamp: Any) -> datetime:
    if timestamp is None:
        raise ValueError("Missing observation timestamp")

    numeric = float(timestamp)
    # Ambient Weather emits milliseconds since epoch; fall back to seconds if already small.
    if numeric > 10**12:
        numeric /= 1000.0

    return datetime.fromtimestamp(numeric, tz=timezone.utc)


def _extract_coords(info: Mapping[str, Any]) -> tuple[float, float]:
    coords: Any = info.get("coords")
    if isinstance(coords, Mapping):
        nested = coords.get("coords")
        if isinstance(nested, Mapping):
            lat = nested.get("lat") or nested.get("latitude")
            lon = nested.get("lon") or nested.get("longitude")
        else:
            lat = coords.get("lat") or coords.get("latitude")
            lon = coords.get("lon") or coords.get("longitude")
    elif isinstance(coords, Sequence) and not isinstance(coords, (str, bytes)):
        if len(coords) < 2:
            lat = lon = None
        else:
            lat, lon = coords[0], coords[1]
    else:
        lat = lon = None

    if lat is None or lon is None:
        raise ValueError("Missing coordinates for device")

    return float(lat), float(lon)


def _select_device(devices: Sequence[Mapping[str, Any]], preferred_mac: Optional[str]) -> Mapping[str, Any]:
    if not devices:
        raise ValueError("No devices found in payload")

    # Selection rule: prefer an explicit MAC (env override or parameter), otherwise choose
    # the first device after sorting by MAC address for determinism.
    if preferred_mac:
        for device in devices:
            mac = str(device.get("macAddress") or "")
            if mac.lower() == preferred_mac.lower():
                return device
        raise ValueError(f"Device with MAC {preferred_mac} not found")

    return sorted(devices, key=lambda dev: str(dev.get("macAddress") or ""))[0]


def map_ambient_weather_observation(
    payload: Sequence[Mapping[str, Any]], *, provider: str = "ambient_weather", device_mac: Optional[str] = None
) -> Observation:
    preferred_mac = device_mac or os.getenv("WX_AMBIENT_DEVICE_MAC")
    device = _select_device(payload, preferred_mac)

    last_data: MutableMapping[str, Any] = device.get("lastData") or {}
    if not last_data:
        raise ValueError("Device payload missing lastData")

    info: Mapping[str, Any] = device.get("info") or {}
    latitude, longitude = _extract_coords(info)

    observed_at = _parse_observed_at(last_data.get("dateutc"))

    temperature_f = _to_optional_float(last_data.get("tempf"))
    if temperature_f is None:
        temperature_f = _to_optional_float(last_data.get("tempOut"))
    if temperature_f is None:
        temperature_c_metric = _to_optional_float(last_data.get("tempc"))
    else:
        temperature_c_metric = None

    dewpoint_f = _to_optional_float(last_data.get("dewPoint"))
    if dewpoint_f is None:
        dewpoint_f = _to_optional_float(last_data.get("dewptf"))
    if dewpoint_f is None:
        dewpoint_c_metric = _to_optional_float(last_data.get("dewpt"))
    else:
        dewpoint_c_metric = None

    wind_speed_mph = _to_optional_float(last_data.get("windspeedmph"))
    if wind_speed_mph is None:
        wind_speed_mph = _to_optional_float(last_data.get("windSpeed"))

    pressure_inhg = _to_optional_float(last_data.get("baromrelin"))
    if pressure_inhg is None:
        pressure_inhg = _to_optional_float(last_data.get("baromabsin"))
    if pressure_inhg is None:
        pressure_inhg = _to_optional_float(last_data.get("barometer"))

    precipitation_in = _to_optional_float(last_data.get("hourlyrainin"))
    if precipitation_in is None:
        precipitation_in = _to_optional_float(last_data.get("hourlyrain"))

    return Observation(
        provider=provider,
        station=info.get("name") or device.get("macAddress"),
        location=Location(latitude=latitude, longitude=longitude),
        observed_at=observed_at,
        temperature_c=temperature_c_metric if temperature_c_metric is not None else _f_to_c(temperature_f),
        dewpoint_c=dewpoint_c_metric if dewpoint_c_metric is not None else _f_to_c(dewpoint_f),
        wind_speed_kph=_mph_to_kph(wind_speed_mph),
        wind_direction_deg=_to_optional_int(last_data.get("winddir")),
        pressure_kpa=_inHg_to_kpa(pressure_inhg),
        relative_humidity=_to_optional_float(last_data.get("humidity")),
        visibility_km=None,
        condition=None,
        precipitation_last_hour_mm=_inches_to_mm(precipitation_in),
    )


__all__ = ["map_ambient_weather_observation"]
