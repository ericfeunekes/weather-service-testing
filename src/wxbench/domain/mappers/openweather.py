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


def _weather_code(payload: Mapping[str, Any]) -> Optional[int]:
    weather: Sequence[Mapping[str, Any]] = payload.get("weather") or []
    if not weather:
        return None
    return _to_optional_int(weather[0].get("id"))


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


def _extract_onecall_precipitation(values: Mapping[str, Any]) -> Optional[float]:
    rain = values.get("rain")
    if isinstance(rain, Mapping):
        return _to_optional_float(rain.get("1h") or rain.get("3h"))
    if isinstance(rain, (int, float)):
        return _to_optional_float(rain)
    snow = values.get("snow")
    if isinstance(snow, Mapping):
        return _to_optional_float(snow.get("1h") or snow.get("3h"))
    if isinstance(snow, (int, float)):
        return _to_optional_float(snow)
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
    clouds: Mapping[str, Any] = payload.get("clouds") or {}

    return Observation(
        provider=provider,
        station=payload.get("name"),
        location=Location(latitude=float(coords["lat"]), longitude=float(coords["lon"])),
        observed_at=observed_at,
        temperature_c=_kelvin_to_celsius(_to_optional_float(main.get("temp"))),
        temperature_apparent_c=_kelvin_to_celsius(_to_optional_float(main.get("feels_like"))),
        dewpoint_c=None,
        wind_speed_kph=_ms_to_kph(_to_optional_float(wind.get("speed"))),
        wind_direction_deg=_to_optional_int(wind.get("deg")),
        wind_gust_kph=_ms_to_kph(_to_optional_float(wind.get("gust"))),
        pressure_kpa=_hpa_to_kpa(_to_optional_float(main.get("pressure"))),
        pressure_sea_level_kpa=_hpa_to_kpa(_to_optional_float(main.get("pressure"))),
        relative_humidity=_to_optional_float(main.get("humidity")),
        visibility_km=_meters_to_km(_to_optional_float(payload.get("visibility"))),
        cloud_cover_pct=_to_optional_float(clouds.get("all")),
        condition=_weather_summary(payload),
        condition_code=_weather_code(payload),
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
        clouds: Mapping[str, Any] = entry.get("clouds") or {}
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
                condition_code=_weather_code(entry),
                wind_speed_kph=_ms_to_kph(_to_optional_float(wind.get("speed"))),
                wind_direction_deg=_to_optional_int(wind.get("deg")),
                wind_gust_kph=_ms_to_kph(_to_optional_float(wind.get("gust"))),
                relative_humidity=_to_optional_float(main.get("humidity")),
                pressure_sea_level_kpa=_hpa_to_kpa(_to_optional_float(main.get("pressure"))),
                cloud_cover_pct=_to_optional_float(clouds.get("all")),
            )
        )

    return normalized


def map_openweather_onecall_hourly(
    payload: Mapping[str, Any], *, provider: str = "openweather", iso_parser: Optional[IsoParser] = None
) -> list[ForecastPeriod]:
    latitude = payload.get("lat")
    longitude = payload.get("lon")
    if latitude is None or longitude is None:
        raise ValueError("Missing coordinates for One Call hourly forecast")

    intervals: Sequence[Mapping[str, Any]] = payload.get("hourly") or []
    if not intervals:
        return []

    issued_at = _timestamp_to_datetime(intervals[0].get("dt"))
    normalized: list[ForecastPeriod] = []
    for entry in intervals:
        start_time = _timestamp_to_datetime(entry.get("dt"))
        end_time = start_time + timedelta(hours=1)

        pop = _to_optional_float(entry.get("pop"))
        if pop is not None:
            pop *= 100.0

        normalized.append(
            ForecastPeriod(
                provider=provider,
                location=Location(latitude=float(latitude), longitude=float(longitude)),
                issued_at=issued_at,
                start_time=start_time,
                end_time=end_time,
                temperature_c=_to_optional_float(entry.get("temp")),
                temperature_apparent_c=_to_optional_float(entry.get("feels_like")),
                temperature_high_c=None,
                temperature_low_c=None,
                dewpoint_c=_to_optional_float(entry.get("dew_point")),
                precipitation_probability=pop,
                precipitation_mm=_extract_onecall_precipitation(entry),
                summary=_weather_summary(entry),
                condition_code=_weather_code(entry),
                wind_speed_kph=_ms_to_kph(_to_optional_float(entry.get("wind_speed"))),
                wind_direction_deg=_to_optional_int(entry.get("wind_deg")),
                wind_gust_kph=_ms_to_kph(_to_optional_float(entry.get("wind_gust"))),
                uv_index=_to_optional_float(entry.get("uvi")),
                relative_humidity=_to_optional_float(entry.get("humidity")),
                pressure_sea_level_kpa=_hpa_to_kpa(_to_optional_float(entry.get("pressure"))),
                cloud_cover_pct=_to_optional_float(entry.get("clouds")),
                visibility_km=_meters_to_km(_to_optional_float(entry.get("visibility"))),
            )
        )

    return normalized


def map_openweather_onecall_daily(
    payload: Mapping[str, Any], *, provider: str = "openweather", iso_parser: Optional[IsoParser] = None
) -> list[ForecastPeriod]:
    latitude = payload.get("lat")
    longitude = payload.get("lon")
    if latitude is None or longitude is None:
        raise ValueError("Missing coordinates for One Call daily forecast")

    intervals: Sequence[Mapping[str, Any]] = payload.get("daily") or []
    if not intervals:
        return []

    issued_at = _timestamp_to_datetime(intervals[0].get("dt"))
    normalized: list[ForecastPeriod] = []
    for entry in intervals:
        start_time = _timestamp_to_datetime(entry.get("dt"))
        end_time = start_time + timedelta(days=1)

        temp_block: Mapping[str, Any] = entry.get("temp") or {}
        pop = _to_optional_float(entry.get("pop"))
        if pop is not None:
            pop *= 100.0

        normalized.append(
            ForecastPeriod(
                provider=provider,
                location=Location(latitude=float(latitude), longitude=float(longitude)),
                issued_at=issued_at,
                start_time=start_time,
                end_time=end_time,
                temperature_c=_to_optional_float(temp_block.get("day")),
                temperature_apparent_c=_to_optional_float((entry.get("feels_like") or {}).get("day")),
                temperature_high_c=_to_optional_float(temp_block.get("max")),
                temperature_low_c=_to_optional_float(temp_block.get("min")),
                dewpoint_c=_to_optional_float(entry.get("dew_point")),
                precipitation_probability=pop,
                precipitation_mm=_extract_onecall_precipitation(entry),
                summary=_weather_summary(entry),
                condition_code=_weather_code(entry),
                wind_speed_kph=_ms_to_kph(_to_optional_float(entry.get("wind_speed"))),
                wind_direction_deg=_to_optional_int(entry.get("wind_deg")),
                wind_gust_kph=_ms_to_kph(_to_optional_float(entry.get("wind_gust"))),
                uv_index=_to_optional_float(entry.get("uvi")),
                relative_humidity=_to_optional_float(entry.get("humidity")),
                pressure_sea_level_kpa=_hpa_to_kpa(_to_optional_float(entry.get("pressure"))),
                cloud_cover_pct=_to_optional_float(entry.get("clouds")),
            )
        )

    return normalized


__all__ = [
    "map_openweather_observation",
    "map_openweather_forecast",
    "map_openweather_onecall_hourly",
    "map_openweather_onecall_daily",
]
