"""Mapping helpers for MSC GeoMet provider payloads."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Callable, Iterable, Mapping, MutableMapping, Optional, Sequence

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


def _extract_condition(present_weather: Any) -> Optional[str]:
    if not present_weather:
        return None
    if isinstance(present_weather, Sequence):
        first = present_weather[0]
    else:
        first = present_weather
    if isinstance(first, Mapping):
        for key in ("value", "text", "description"):
            if first.get(key):
                return str(first[key])
        return None
    return str(first)


def _first_present(mapping: Mapping[str, Any], keys: Sequence[str]) -> Any:
    for key in keys:
        if key in mapping and mapping[key] is not None:
            return mapping[key]
    return None


def map_msc_geomet_observation(
    feature: Mapping[str, Any], *, provider: str = "msc_geomet", iso_parser: Optional[IsoParser] = None
) -> Observation:
    properties: MutableMapping[str, Any] = feature.get("properties") or {}
    geometry: MutableMapping[str, Any] = feature.get("geometry") or {}
    coordinates: Iterable[Any] = geometry.get("coordinates") or []
    coords = list(coordinates)

    if len(coords) < 2:
        raise ValueError("Missing coordinates for observation")

    observed_raw = _first_present(
        properties,
        ("observationTime", "time", "timestamp", "datetime"),
    )
    if not observed_raw:
        raise ValueError("Missing observation time")

    observed_at = _parse_iso8601(str(observed_raw), iso_parser)
    wind = properties.get("wind") or {}

    return Observation(
        provider=provider,
        station=_first_present(properties, ("stationIdentifier", "station")),
        location=Location(latitude=float(coords[1]), longitude=float(coords[0])),
        observed_at=observed_at,
        temperature_c=_to_optional_float(_first_present(properties, ("airTemperature", "temperature"))),
        dewpoint_c=_to_optional_float(_first_present(properties, ("dewpointTemperature", "dewpoint"))),
        wind_speed_kph=_to_optional_float(wind.get("speed")),
        wind_direction_deg=_to_optional_int(wind.get("direction")),
        pressure_kpa=_to_optional_float(_first_present(properties, ("seaLevelPressure", "pressure"))),
        relative_humidity=_to_optional_float(properties.get("relativeHumidity")),
        visibility_km=_to_optional_float(properties.get("visibility")),
        condition=_extract_condition(properties.get("presentWeather")),
        precipitation_last_hour_mm=_to_optional_float(properties.get("precipitationLastHour")),
    )


def map_msc_geomet_forecast(
    feature: Mapping[str, Any], *, provider: str = "msc_geomet", iso_parser: Optional[IsoParser] = None
) -> list[ForecastPeriod]:
    properties: MutableMapping[str, Any] = feature.get("properties") or {}
    geometry: MutableMapping[str, Any] = feature.get("geometry") or {}
    coordinates: Iterable[Any] = geometry.get("coordinates") or []
    coords = list(coordinates)

    if len(coords) < 2:
        raise ValueError("Missing coordinates for forecast")

    issued_raw = _first_present(properties, ("forecastIssueTime", "issueTime", "issuedAt"))
    if not issued_raw:
        raise ValueError("Missing forecast issue time")
    issued_at = _parse_iso8601(str(issued_raw), iso_parser)

    periods: Iterable[Mapping[str, Any]] = properties.get("periods") or []
    normalized: list[ForecastPeriod] = []
    for period in periods:
        start_raw = _first_present(period, ("start", "startTime", "validTime"))
        end_raw = _first_present(period, ("end", "endTime", "validEndTime")) or start_raw
        if not start_raw:
            raise ValueError("Forecast period missing start time")

        start_time = _parse_iso8601(str(start_raw), iso_parser)
        end_time = _parse_iso8601(str(end_raw), iso_parser)
        wind = period.get("wind") or {}

        normalized.append(
            ForecastPeriod(
                provider=provider,
                location=Location(latitude=float(coords[1]), longitude=float(coords[0])),
                issued_at=issued_at,
                start_time=start_time,
                end_time=end_time,
                temperature_c=_to_optional_float(period.get("temperature")),
                temperature_high_c=_to_optional_float(period.get("temperatureHigh")),
                temperature_low_c=_to_optional_float(period.get("temperatureLow")),
                precipitation_probability=_to_optional_float(
                    _first_present(period, ("probabilityOfPrecipitation", "pop"))
                ),
                precipitation_mm=_to_optional_float(
                    _first_present(period, ("totalPrecipitation", "precipitationAmount"))
                ),
                summary=_first_present(period, ("summary", "textSummary")),
                wind_speed_kph=_to_optional_float(wind.get("speed")),
                wind_direction_deg=_to_optional_int(wind.get("direction")),
            )
        )

    return normalized


__all__ = ["map_msc_geomet_observation", "map_msc_geomet_forecast"]
