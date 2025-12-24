"""Mapping helpers for MSC GeoMet provider payloads."""
from __future__ import annotations

from datetime import datetime, timedelta
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
    value = _unwrap_value(value)
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _to_optional_int(value: Any) -> Optional[int]:
    value = _unwrap_value(value)
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _unwrap_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        if "textSummary" in value:
            return _unwrap_value(value.get("textSummary"))
        if "value" in value:
            return _unwrap_value(value.get("value"))
        if "en" in value:
            return _unwrap_value(value.get("en"))
    return value


def _extract_condition(present_weather: Any) -> Optional[str]:
    if not present_weather:
        return None
    present_weather = _unwrap_value(present_weather)
    if isinstance(present_weather, Sequence) and not isinstance(present_weather, (str, bytes)):
        present_weather = present_weather[0]
    if isinstance(present_weather, Mapping):
        for key in ("value", "text", "description"):
            candidate = present_weather.get(key)
            if candidate:
                return str(_unwrap_value(candidate))
        return None
    return str(present_weather)


def _first_present(mapping: Mapping[str, Any], keys: Sequence[str]) -> Any:
    for key in keys:
        if key in mapping and mapping[key] is not None:
            return _unwrap_value(mapping[key])
    return None


def _select_temperature(temperatures: Iterable[Mapping[str, Any]], category: str | None = None) -> Optional[float]:
    for entry in temperatures:
        temp_class = entry.get("class") or {}
        class_value = _unwrap_value(temp_class)
        if category is None or str(class_value).lower() == category:
            candidate = entry.get("value") if "value" in entry else entry
            value = _unwrap_value(candidate)
            numeric = _to_optional_float(value)
            if numeric is not None:
                return numeric
    return None


def map_msc_geomet_observation(
    feature: Mapping[str, Any], *, provider: str = "msc_geomet", iso_parser: Optional[IsoParser] = None
) -> Observation:
    properties: MutableMapping[str, Any] = feature.get("properties") or {}
    current_conditions = properties.get("currentConditions") or {}
    merged_properties: MutableMapping[str, Any] = {**properties, **current_conditions}
    geometry: MutableMapping[str, Any] = feature.get("geometry") or {}
    coordinates: Iterable[Any] = geometry.get("coordinates") or []
    coords = list(coordinates)

    if len(coords) < 2:
        raise ValueError("Missing coordinates for observation")

    observed_raw = _first_present(
        merged_properties,
        ("observationTime", "time", "timestamp", "datetime"),
    )
    if not observed_raw:
        raise ValueError("Missing observation time")

    observed_at = _parse_iso8601(str(observed_raw), iso_parser)
    wind = merged_properties.get("wind") or merged_properties.get("winds") or {}

    return Observation(
        provider=provider,
        station=
        _first_present(
            merged_properties,
            (
                "stationIdentifier",
                "station",
                "identifier",
            ),
        )
        or _unwrap_value((properties.get("name") or {}).get("en")),
        location=Location(latitude=float(coords[1]), longitude=float(coords[0])),
        observed_at=observed_at,
        temperature_c=_to_optional_float(_first_present(merged_properties, ("airTemperature", "temperature"))),
        dewpoint_c=_to_optional_float(_first_present(merged_properties, ("dewpointTemperature", "dewpoint"))),
        wind_speed_kph=_to_optional_float(_first_present(wind, ("speed",))),
        wind_direction_deg=_to_optional_int(_first_present(wind, ("direction",))),
        pressure_kpa=_to_optional_float(_first_present(merged_properties, ("seaLevelPressure", "pressure"))),
        relative_humidity=_to_optional_float(merged_properties.get("relativeHumidity")),
        visibility_km=_to_optional_float(merged_properties.get("visibility")),
        condition=_extract_condition(
            merged_properties.get("presentWeather")
            or merged_properties.get("condition")
            or (merged_properties.get("condition", {}) if isinstance(merged_properties.get("condition"), Mapping) else None)
        ),
        precipitation_last_hour_mm=_to_optional_float(merged_properties.get("precipitationLastHour")),
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

    forecast_group = properties.get("forecastGroup") or {}

    issued_raw = _first_present(
        forecast_group if forecast_group else properties,
        ("forecastIssueTime", "issueTime", "issuedAt", "timestamp"),
    )
    if not issued_raw:
        raise ValueError("Missing forecast issue time")
    issued_at = _parse_iso8601(str(issued_raw), iso_parser)

    periods: Iterable[Mapping[str, Any]] = (
        forecast_group.get("periods")
        or forecast_group.get("forecasts")
        or properties.get("periods")
        or []
    )
    normalized: list[ForecastPeriod] = []
    for index, period in enumerate(periods):
        if not isinstance(period, Mapping):
            continue
        start_raw = _first_present(period, ("start", "startTime", "validTime", "periodStart"))
        end_raw = _first_present(period, ("end", "endTime", "validEndTime", "periodEnd")) or start_raw

        if start_raw:
            start_time = _parse_iso8601(str(start_raw), iso_parser)
        elif forecast_group:
            start_time = issued_at + timedelta(hours=index * 12)
        else:
            raise ValueError("Forecast period missing start time")

        if end_raw:
            end_time = _parse_iso8601(str(end_raw), iso_parser)
        elif forecast_group:
            end_time = start_time + timedelta(hours=12)
        else:
            raise ValueError("Forecast period missing end time")

        raw_winds = period.get("winds")
        wind_entries: list[Mapping[str, Any]] = []
        if isinstance(raw_winds, list):
            wind_entries = [entry for entry in raw_winds if isinstance(entry, Mapping)]
        elif isinstance(raw_winds, Mapping):
            nested_wind = raw_winds.get("wind")
            if isinstance(nested_wind, list):
                wind_entries = [entry for entry in nested_wind if isinstance(entry, Mapping)]
        wind_entry = wind_entries[0] if wind_entries else period.get("wind") or {}

        temperature_block = period.get("temperatures") or {}
        temps: Iterable[Mapping[str, Any]] = (
            temperature_block.get("temperature") if isinstance(temperature_block, Mapping) else []
        ) or []

        precipitation = period.get("precipitation") or {}
        precipitation_amounts = precipitation.get("precipAmounts") or []
        pop_value = period.get("pop") or {}

        temperature_c = _select_temperature(temps, None)
        if temperature_c is None:
            temperature_c = _to_optional_float(period.get("temperature"))

        temperature_high_c = _select_temperature(temps, "high") or _to_optional_float(period.get("temperatureHigh"))
        temperature_low_c = _select_temperature(temps, "low") or _to_optional_float(period.get("temperatureLow"))

        precipitation_probability = _to_optional_float(
            _first_present(pop_value, ("value",)) if isinstance(pop_value, Mapping) else pop_value
        )
        if precipitation_probability is None:
            precipitation_probability = _to_optional_float(
                _first_present(period, ("probabilityOfPrecipitation", "pop"))
            )

        precipitation_mm = _to_optional_float(precipitation_amounts[0] if precipitation_amounts else None)
        if precipitation_mm is None:
            precipitation_mm = _to_optional_float(
                _first_present(period, ("totalPrecipitation", "precipitationAmount"))
            )

        summary = _extract_condition(period.get("summary") or period.get("textSummary") or period.get("cloudPrecip"))
        wind_speed_kph = _to_optional_float(_first_present(wind_entry, ("speed",)))
        if wind_speed_kph is None:
            wind_speed_kph = _to_optional_float(period.get("windSpeed"))

        wind_direction_deg = _to_optional_int(_first_present(wind_entry, ("direction",)))
        if wind_direction_deg is None:
            wind_direction_deg = _to_optional_int(period.get("windDirection"))

        normalized.append(
            ForecastPeriod(
                provider=provider,
                location=Location(latitude=float(coords[1]), longitude=float(coords[0])),
                issued_at=issued_at,
                start_time=start_time,
                end_time=end_time,
                temperature_c=temperature_c,
                temperature_high_c=temperature_high_c,
                temperature_low_c=temperature_low_c,
                precipitation_probability=precipitation_probability,
                precipitation_mm=precipitation_mm,
                summary=summary,
                wind_speed_kph=wind_speed_kph,
                wind_direction_deg=wind_direction_deg,
            )
        )

    return normalized


__all__ = ["map_msc_geomet_observation", "map_msc_geomet_forecast"]
