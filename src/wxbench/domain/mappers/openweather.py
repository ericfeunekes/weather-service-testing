"""Mapping helpers for OpenWeather payloads."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Mapping, MutableMapping, Optional, Sequence

from wxbench.domain.models import ForecastPeriod, Location, Observation

IsoParser = Callable[[str], datetime]


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


def _kelvin_to_celsius(value: Optional[float]) -> Optional[float]:
    if value is None:
        return None
    return value - 273.15


def _meters_to_km(value: Optional[float]) -> Optional[float]:
    if value is None:
        return None
    return value / 1000.0


def _hpa_to_kpa(value: Optional[float]) -> Optional[float]:
    if value is None:
        return None
    return value / 10.0


def _ms_to_kph(value: Optional[float]) -> Optional[float]:
    if value is None:
        return None
    return value * 3.6


def _weather_summary(payload: Mapping[str, Any]) -> Optional[str]:
    weather: Sequence[Mapping[str, Any]] = payload.get("weather") or []
    if not weather:
        return None
    first = weather[0]
    return str(first.get("description") or first.get("main"))


def _timestamp_to_datetime(value: Any) -> datetime:
    if value is None:
        raise ValueError("Timestamp missing")
    return datetime.fromtimestamp(int(value), tz=timezone.utc)


def _extract_precipitation(values: Mapping[str, Any]) -> Optional[float]:
    if "rain" in values:
        rain = values.get("rain") or {}
        if isinstance(rain, Mapping):
            return _to_optional_float(rain.get("1h") or rain.get("3h"))
    if "snow" in values:
        snow = values.get("snow") or {}
        if isinstance(snow, Mapping):
            return _to_optional_float(snow.get("1h") or snow.get("3h"))
    return None


def map_openweather_observation(
    payload: Mapping[str, Any], *, provider: str = "openweather", iso_parser: Optional[IsoParser] = None
) -> Observation:
    coords: MutableMapping[str, Any] = payload.get("coord") or {}
    if "lat" not in coords or "lon" not in coords:
        raise ValueError("Missing coordinates for observation")

    observed_at = _timestamp_to_datetime(payload.get("dt"))
    main: Mapping[str, Any] = payload.get("main") or {}
    wind: Mapping[str, Any] = payload.get("wind") or {}

    return Observation(
        provider=provider,
        station=payload.get("name"),
        location=Location(latitude=float(coords["lat"]), longitude=float(coords["lon"])),
        observed_at=observed_at,
        temperature_c=_kelvin_to_celsius(_to_optional_float(main.get("temp"))),
        dewpoint_c=None,
        wind_speed_kph=_ms_to_kph(_to_optional_float(wind.get("speed"))),
        wind_direction_deg=_to_optional_int(wind.get("deg")),
        pressure_kpa=_hpa_to_kpa(_to_optional_float(main.get("pressure"))),
        relative_humidity=_to_optional_float(main.get("humidity")),
        visibility_km=_meters_to_km(_to_optional_float(payload.get("visibility"))),
        condition=_weather_summary(payload),
        precipitation_last_hour_mm=_extract_precipitation(payload),
    )


def map_openweather_forecast(
    payload: Mapping[str, Any], *, provider: str = "openweather", iso_parser: Optional[IsoParser] = None
) -> list[ForecastPeriod]:
    city: Mapping[str, Any] = payload.get("city") or {}
    coords: MutableMapping[str, Any] = city.get("coord") or {}
    periods: Sequence[Mapping[str, Any]] = payload.get("list") or []

    if "lat" not in coords or "lon" not in coords:
        raise ValueError("Missing coordinates for forecast")

    if not periods:
        return []

    issued_at = _timestamp_to_datetime(periods[0].get("dt"))

    normalized: list[ForecastPeriod] = []
    for entry in periods:
        start_time = _timestamp_to_datetime(entry.get("dt"))
        end_time = start_time + timedelta(hours=3)

        main: Mapping[str, Any] = entry.get("main") or {}
        wind: Mapping[str, Any] = entry.get("wind") or {}
        precipitation = _extract_precipitation(entry)
        pop = _to_optional_float(entry.get("pop"))
        if pop is not None:
            pop *= 100.0

        normalized.append(
            ForecastPeriod(
                provider=provider,
                location=Location(latitude=float(coords["lat"]), longitude=float(coords["lon"])),
                issued_at=issued_at,
                start_time=start_time,
                end_time=end_time,
                temperature_c=_kelvin_to_celsius(_to_optional_float(main.get("temp"))),
                temperature_high_c=_kelvin_to_celsius(_to_optional_float(main.get("temp_max"))),
                temperature_low_c=_kelvin_to_celsius(_to_optional_float(main.get("temp_min"))),
                precipitation_probability=pop,
                precipitation_mm=precipitation,
                summary=_weather_summary(entry),
                wind_speed_kph=_ms_to_kph(_to_optional_float(wind.get("speed"))),
                wind_direction_deg=_to_optional_int(wind.get("deg")),
            )
        )

    return normalized


__all__ = ["map_openweather_observation", "map_openweather_forecast"]
