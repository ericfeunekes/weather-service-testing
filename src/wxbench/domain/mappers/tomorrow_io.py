"""Mapping helpers for Tomorrow.io payloads."""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Callable, Iterable, Mapping, Optional, Sequence

from wxbench.domain.models import ForecastPeriod, Location, Observation

IsoParser = Callable[[str], datetime]


def _default_iso8601_parser(value: str) -> datetime:
    cleaned = value.replace("Z", "+00:00") if value.endswith("Z") else value
    return datetime.fromisoformat(cleaned)


def _parse_iso8601(value: str, iso_parser: Optional[IsoParser]) -> datetime:
    parser = iso_parser or _default_iso8601_parser
    return parser(value)


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


def _ms_to_kph(value: Optional[float]) -> Optional[float]:
    if value is None:
        return None
    return value * 3.6


def _meters_to_km(value: Optional[float]) -> Optional[float]:
    if value is None:
        return None
    return value / 1000.0


def _hpa_to_kpa(value: Optional[float]) -> Optional[float]:
    if value is None:
        return None
    return value / 10.0


_WEATHER_CODE_TO_DESCRIPTION: Mapping[int, str] = {
    0: "Unknown",
    1000: "Clear",
    1100: "Mostly Clear",
    1101: "Partly Cloudy",
    1102: "Mostly Cloudy",
    1001: "Cloudy",
    2000: "Fog",
    2100: "Light Fog",
    4000: "Drizzle",
    4001: "Rain",
    4200: "Light Rain",
    4201: "Heavy Rain",
    5000: "Snow",
    5001: "Flurries",
    5100: "Light Snow",
    5101: "Heavy Snow",
    6000: "Freezing Drizzle",
    6001: "Freezing Rain",
    6200: "Light Freezing Rain",
    6201: "Heavy Freezing Rain",
    7000: "Ice Pellets",
    7101: "Heavy Ice Pellets",
    7102: "Light Ice Pellets",
}


def _describe_weather_code(code: Any) -> Optional[str]:
    numeric = _to_optional_int(code)
    if numeric is None:
        return None
    return _WEATHER_CODE_TO_DESCRIPTION.get(numeric, str(numeric))


def map_tomorrow_io_observation(
    payload: Mapping[str, Any], *, provider: str = "tomorrow_io", iso_parser: Optional[IsoParser] = None
) -> Observation:
    data: Mapping[str, Any] = payload.get("data") or {}
    values: Mapping[str, Any] = data.get("values") or {}
    location: Mapping[str, Any] = data.get("location") or {}

    if "lat" not in location or "lon" not in location:
        raise ValueError("Missing coordinates for observation")

    observed_raw = data.get("time")
    if not observed_raw:
        raise ValueError("Missing observation time")

    observed_at = _parse_iso8601(str(observed_raw), iso_parser)

    temperature = _to_optional_float(values.get("temperature"))
    dewpoint = _to_optional_float(values.get("dewPoint"))
    wind_speed = _ms_to_kph(_to_optional_float(values.get("windSpeed")))
    wind_direction = _to_optional_int(values.get("windDirection"))
    pressure = _hpa_to_kpa(_to_optional_float(values.get("pressureSurfaceLevel")))
    humidity = _to_optional_float(values.get("humidity"))
    visibility = _meters_to_km(_to_optional_float(values.get("visibility")))
    condition = _describe_weather_code(values.get("weatherCode"))
    precipitation_hour = _to_optional_float(values.get("precipitationIntensity"))

    return Observation(
        provider=provider,
        station=location.get("name"),
        location=Location(latitude=float(location["lat"]), longitude=float(location["lon"])),
        observed_at=observed_at,
        temperature_c=temperature,
        dewpoint_c=dewpoint,
        wind_speed_kph=wind_speed,
        wind_direction_deg=wind_direction,
        pressure_kpa=pressure,
        relative_humidity=humidity,
        visibility_km=visibility,
        condition=condition,
        precipitation_last_hour_mm=precipitation_hour,
    )


def _infer_end_time(
    index: int,
    intervals: Sequence[Mapping[str, Any]],
    start_time: datetime,
    timestep: Optional[str],
    iso_parser: Optional[IsoParser],
) -> datetime:
    if index + 1 < len(intervals):
        next_raw = intervals[index + 1].get("startTime")
        if next_raw:
            return _parse_iso8601(str(next_raw), iso_parser)

    if timestep and timestep.endswith("h"):
        hours = _to_optional_float(timestep[:-1])
        if hours:
            return start_time + timedelta(hours=hours)
    if timestep and timestep.endswith("m"):
        minutes = _to_optional_float(timestep[:-1])
        if minutes:
            return start_time + timedelta(minutes=minutes)

    return start_time


def map_tomorrow_io_forecast(
    payload: Mapping[str, Any], *, provider: str = "tomorrow_io", iso_parser: Optional[IsoParser] = None
) -> list[ForecastPeriod]:
    data: Mapping[str, Any] = payload.get("data") or {}
    timelines: Sequence[Mapping[str, Any]] = data.get("timelines") or []
    location: Mapping[str, Any] = data.get("location") or {}

    if "lat" not in location or "lon" not in location:
        raise ValueError("Missing coordinates for forecast")

    if not timelines:
        return []

    issued_raw = data.get("time") or timelines[0].get("startTime")
    if not issued_raw:
        raise ValueError("Missing forecast issue time")
    issued_at = _parse_iso8601(str(issued_raw), iso_parser)

    normalized: list[ForecastPeriod] = []
    for timeline in timelines:
        timestep = timeline.get("timestep")
        intervals: Sequence[Mapping[str, Any]] = timeline.get("intervals") or []
        for index, interval in enumerate(intervals):
            start_raw = interval.get("startTime")
            if not start_raw:
                raise ValueError("Forecast interval missing start time")

            start_time = _parse_iso8601(str(start_raw), iso_parser)
            end_time = _infer_end_time(index, intervals, start_time, str(timestep) if timestep else None, iso_parser)

            values: Mapping[str, Any] = interval.get("values") or {}
            temp = _to_optional_float(values.get("temperature"))
            pop = _to_optional_float(values.get("precipitationProbability"))
            precip_intensity = _to_optional_float(values.get("precipitationIntensity"))
            wind_speed = _ms_to_kph(_to_optional_float(values.get("windSpeed")))
            wind_dir = _to_optional_int(values.get("windDirection"))
            condition = _describe_weather_code(values.get("weatherCode"))

            precipitation_mm = precip_intensity
            if precip_intensity is not None and end_time != start_time:
                duration_hours = (end_time - start_time).total_seconds() / 3600.0
                precipitation_mm = precip_intensity * duration_hours

            normalized.append(
                ForecastPeriod(
                    provider=provider,
                    location=Location(latitude=float(location["lat"]), longitude=float(location["lon"])),
                    issued_at=issued_at,
                    start_time=start_time,
                    end_time=end_time,
                    temperature_c=temp,
                    precipitation_probability=pop,
                    precipitation_mm=precipitation_mm,
                    summary=condition,
                    wind_speed_kph=wind_speed,
                    wind_direction_deg=wind_dir,
                )
            )

    return normalized


__all__ = ["map_tomorrow_io_observation", "map_tomorrow_io_forecast"]
