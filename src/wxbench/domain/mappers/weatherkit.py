"""Mapping helpers for WeatherKit REST payloads."""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Callable, Mapping, Optional, Sequence

from wxbench.domain.mappers._common import _to_optional_float, _to_optional_int
from wxbench.domain.models import ForecastPeriod, Location, Observation, WeatherAlert

IsoParser = Callable[[str], datetime]


def _default_iso8601_parser(value: str) -> datetime:
    cleaned = value.replace("Z", "+00:00") if value.endswith("Z") else value
    return datetime.fromisoformat(cleaned)


def _parse_iso8601(value: str, iso_parser: Optional[IsoParser]) -> datetime:
    parser = iso_parser or _default_iso8601_parser
    return parser(value)


def _fraction_to_percent(value: Any) -> Optional[float]:
    numeric = _to_optional_float(value)
    if numeric is None:
        return None
    return numeric * 100.0


def _millibars_to_kpa(value: Any) -> Optional[float]:
    numeric = _to_optional_float(value)
    if numeric is None:
        return None
    return numeric / 10.0


def _meters_to_km(value: Any) -> Optional[float]:
    numeric = _to_optional_float(value)
    if numeric is None:
        return None
    return numeric / 1000.0


def _first_text(*values: Any) -> Optional[str]:
    for value in values:
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return None


def _precip_rate_field(condition: Optional[str]) -> Optional[str]:
    if not condition:
        return "precipitation_rate_rain_mm_hr"
    normalized = str(condition).lower()
    if normalized == "clear":
        return None
    return {
        "precipitation": "precipitation_rate_rain_mm_hr",
        "rain": "precipitation_rate_rain_mm_hr",
        "snow": "precipitation_rate_snow_mm_hr",
        "sleet": "precipitation_rate_sleet_mm_hr",
        "hail": "precipitation_rate_ice_mm_hr",
        "mixed": "precipitation_rate_rain_mm_hr",
    }.get(normalized, "precipitation_rate_rain_mm_hr")


def _extract_location(*sources: Mapping[str, Any]) -> Location:
    for source in sources:
        metadata = source.get("metadata") if isinstance(source, Mapping) else None
        if isinstance(metadata, Mapping):
            latitude = metadata.get("latitude")
            longitude = metadata.get("longitude")
            if latitude is not None and longitude is not None:
                return Location(latitude=float(latitude), longitude=float(longitude))
    raise ValueError("Missing coordinates for WeatherKit data")


def map_weatherkit_observation(
    payload: Mapping[str, Any], *, provider: str = "weatherkit", iso_parser: Optional[IsoParser] = None
) -> Observation:
    current: Mapping[str, Any] = payload.get("currentWeather") or {}
    observed_raw = current.get("asOf")
    if not observed_raw:
        raise ValueError("Missing observation timestamp")

    observed_at = _parse_iso8601(str(observed_raw), iso_parser)
    location = _extract_location(current)

    return Observation(
        provider=provider,
        station=None,
        location=location,
        observed_at=observed_at,
        temperature_c=_to_optional_float(current.get("temperature")),
        temperature_apparent_c=_to_optional_float(current.get("temperatureApparent")),
        dewpoint_c=_to_optional_float(current.get("temperatureDewPoint")),
        wind_speed_kph=_to_optional_float(current.get("windSpeed")),
        wind_direction_deg=_to_optional_int(current.get("windDirection")),
        wind_gust_kph=_to_optional_float(current.get("windGust")),
        pressure_kpa=_millibars_to_kpa(current.get("pressure")),
        pressure_sea_level_kpa=_millibars_to_kpa(current.get("pressure")),
        relative_humidity=_fraction_to_percent(current.get("humidity")),
        visibility_km=_meters_to_km(current.get("visibility")),
        cloud_cover_pct=_fraction_to_percent(current.get("cloudCover")),
        condition=str(current.get("conditionCode")) if current.get("conditionCode") is not None else None,
        precipitation_rate_rain_mm_hr=_to_optional_float(current.get("precipitationIntensity")),
        uv_index=_to_optional_float(current.get("uvIndex")),
        pressure_tendency=str(current.get("pressureTrend")) if current.get("pressureTrend") is not None else None,
    )


def map_weatherkit_hourly_forecast(
    payload: Mapping[str, Any], *, provider: str = "weatherkit", iso_parser: Optional[IsoParser] = None
) -> list[ForecastPeriod]:
    hourly: Mapping[str, Any] = payload.get("forecastHourly") or {}
    hours: Sequence[Mapping[str, Any]] = hourly.get("hours") or []
    if not hours:
        return []

    location = _extract_location(hourly, payload.get("currentWeather") or {})
    issued_raw = hours[0].get("forecastStart")
    if not issued_raw:
        raise ValueError("Missing hourly forecast start time")
    issued_at = _parse_iso8601(str(issued_raw), iso_parser)

    normalized: list[ForecastPeriod] = []
    for entry in hours:
        start_raw = entry.get("forecastStart")
        if not start_raw:
            raise ValueError("Missing hourly forecast start time")
        start_time = _parse_iso8601(str(start_raw), iso_parser)
        end_time = start_time + timedelta(hours=1)

        normalized.append(
            ForecastPeriod(
                provider=provider,
                location=location,
                issued_at=issued_at,
                start_time=start_time,
                end_time=end_time,
                temperature_c=_to_optional_float(entry.get("temperature")),
                temperature_apparent_c=_to_optional_float(entry.get("temperatureApparent")),
                dewpoint_c=_to_optional_float(entry.get("temperatureDewPoint")),
                precipitation_probability=_fraction_to_percent(entry.get("precipitationChance")),
                precipitation_mm=_to_optional_float(entry.get("precipitationAmount")),
                summary=str(entry.get("conditionCode")) if entry.get("conditionCode") is not None else None,
                wind_speed_kph=_to_optional_float(entry.get("windSpeed")),
                wind_direction_deg=_to_optional_int(entry.get("windDirection")),
                wind_gust_kph=_to_optional_float(entry.get("windGust")),
                relative_humidity=_fraction_to_percent(entry.get("humidity")),
                pressure_sea_level_kpa=_millibars_to_kpa(entry.get("pressure")),
                visibility_km=_meters_to_km(entry.get("visibility")),
                cloud_cover_pct=_fraction_to_percent(entry.get("cloudCover")),
                uv_index=_to_optional_float(entry.get("uvIndex")),
                precipitation_rate_snow_mm_hr=_to_optional_float(entry.get("snowfallIntensity")),
            )
        )

    return normalized


def map_weatherkit_daily_forecast(
    payload: Mapping[str, Any], *, provider: str = "weatherkit", iso_parser: Optional[IsoParser] = None
) -> list[ForecastPeriod]:
    daily: Mapping[str, Any] = payload.get("forecastDaily") or {}
    days: Sequence[Mapping[str, Any]] = daily.get("days") or []
    if not days:
        return []

    location = _extract_location(daily, payload.get("currentWeather") or {})
    issued_raw = days[0].get("forecastStart")
    if not issued_raw:
        raise ValueError("Missing daily forecast start time")
    issued_at = _parse_iso8601(str(issued_raw), iso_parser)

    normalized: list[ForecastPeriod] = []
    for entry in days:
        start_raw = entry.get("forecastStart")
        if not start_raw:
            raise ValueError("Missing daily forecast start time")
        start_time = _parse_iso8601(str(start_raw), iso_parser)
        end_raw = entry.get("forecastEnd")
        end_time = (
            _parse_iso8601(str(end_raw), iso_parser)
            if end_raw
            else start_time + timedelta(days=1)
        )

        day_part = entry.get("daytimeForecast") or {}
        overnight_part = entry.get("overnightForecast") or {}

        temp_max = _to_optional_float(entry.get("temperatureMax"))
        temp_min = _to_optional_float(entry.get("temperatureMin"))
        temp_avg = None
        if temp_max is not None and temp_min is not None:
            temp_avg = (temp_max + temp_min) / 2.0

        wind_speed = _to_optional_float(entry.get("windSpeedAvg"))
        if wind_speed is None:
            wind_speed = _to_optional_float(day_part.get("windSpeed"))
        if wind_speed is None:
            wind_speed = _to_optional_float(entry.get("windSpeedMax"))

        wind_gust = _to_optional_float(entry.get("windGustSpeedMax"))
        if wind_gust is None:
            wind_gust = _to_optional_float(day_part.get("windGustSpeedMax"))

        precip_type = _first_text(
            entry.get("precipitationType"),
            day_part.get("precipitationType"),
            overnight_part.get("precipitationType"),
        )

        normalized.append(
            ForecastPeriod(
                provider=provider,
                location=location,
                issued_at=issued_at,
                start_time=start_time,
                end_time=end_time,
                temperature_c=temp_avg,
                temperature_high_c=temp_max,
                temperature_low_c=temp_min,
                precipitation_probability=_fraction_to_percent(entry.get("precipitationChance")),
                precipitation_type=precip_type,
                precipitation_mm=_to_optional_float(entry.get("precipitationAmount")),
                precipitation_amount_snow_mm=_to_optional_float(entry.get("snowfallAmount")),
                summary=str(entry.get("conditionCode")) if entry.get("conditionCode") is not None else None,
                wind_speed_kph=wind_speed,
                wind_direction_deg=_to_optional_int(day_part.get("windDirection")),
                wind_gust_kph=wind_gust,
                relative_humidity=_fraction_to_percent(day_part.get("humidity")),
                cloud_cover_pct=_fraction_to_percent(day_part.get("cloudCover")),
                uv_index=_to_optional_float(entry.get("maxUvIndex")),
            )
        )

    return normalized


def map_weatherkit_next_hour_forecast(
    payload: Mapping[str, Any], *, provider: str = "weatherkit", iso_parser: Optional[IsoParser] = None
) -> list[ForecastPeriod]:
    next_hour: Mapping[str, Any] = payload.get("forecastNextHour") or {}
    minutes: Sequence[Mapping[str, Any]] = next_hour.get("minutes") or []
    if not minutes:
        return []

    summaries: Sequence[Mapping[str, Any]] = next_hour.get("summary") or []
    summary_windows: list[tuple[datetime, datetime, Mapping[str, Any]]] = []
    forecast_end_raw = next_hour.get("forecastEnd")
    forecast_end = _parse_iso8601(str(forecast_end_raw), iso_parser) if forecast_end_raw else None

    summary_entries: list[tuple[datetime, Mapping[str, Any]]] = []
    for entry in summaries:
        start_raw = entry.get("startTime")
        if not start_raw:
            raise ValueError("Missing next hour summary start time")
        start_time = _parse_iso8601(str(start_raw), iso_parser)
        summary_entries.append((start_time, entry))
    summary_entries.sort(key=lambda item: item[0])

    for index, (start_time, entry) in enumerate(summary_entries):
        end_raw = entry.get("endTime")
        if end_raw:
            end_time = _parse_iso8601(str(end_raw), iso_parser)
        elif index + 1 < len(summary_entries):
            end_time = summary_entries[index + 1][0]
        elif forecast_end is not None:
            end_time = forecast_end
        else:
            raise ValueError("Missing next hour summary end time")
        summary_windows.append((start_time, end_time, entry))

    location = _extract_location(next_hour, payload.get("currentWeather") or {}, payload.get("forecastHourly") or {})

    issued_raw = next_hour.get("forecastStart") or minutes[0].get("startTime")
    if not issued_raw:
        raise ValueError("Missing next hour forecast start time")
    issued_at = _parse_iso8601(str(issued_raw), iso_parser)

    normalized: list[ForecastPeriod] = []
    summary_index = 0
    for entry in minutes:
        start_raw = entry.get("startTime")
        if not start_raw:
            raise ValueError("Missing minute forecast start time")
        start_time = _parse_iso8601(str(start_raw), iso_parser)
        end_time = start_time + timedelta(minutes=1)

        condition: Optional[str] = None
        while summary_index < len(summary_windows) and start_time >= summary_windows[summary_index][1]:
            summary_index += 1
        if summary_index < len(summary_windows):
            summary_start, summary_end, summary_entry = summary_windows[summary_index]
            if summary_start <= start_time < summary_end:
                condition = summary_entry.get("condition")

        precipitation_intensity = _to_optional_float(entry.get("precipitationIntensity"))
        precip_field = _precip_rate_field(condition)

        period_kwargs: dict[str, Any] = {
            "provider": provider,
            "location": location,
            "issued_at": issued_at,
            "start_time": start_time,
            "end_time": end_time,
            "precipitation_probability": _fraction_to_percent(entry.get("precipitationChance")),
            "summary": str(condition) if condition is not None else None,
        }
        if precip_field and precipitation_intensity is not None:
            period_kwargs[precip_field] = precipitation_intensity

        normalized.append(ForecastPeriod(**period_kwargs))

    return normalized


def map_weatherkit_alerts(
    payload: Mapping[str, Any], *, provider: str = "weatherkit", iso_parser: Optional[IsoParser] = None
) -> list[WeatherAlert]:
    alerts_block: Mapping[str, Any] = payload.get("weatherAlerts") or {}
    alerts: Sequence[Mapping[str, Any]] = alerts_block.get("alerts") or []
    if not alerts:
        return []

    location = _extract_location(
        alerts_block,
        payload.get("currentWeather") or {},
        payload.get("forecastDaily") or {},
        payload.get("forecastHourly") or {},
    )

    normalized: list[WeatherAlert] = []
    for entry in alerts:
        alert_id = entry.get("id")
        issued_raw = entry.get("issuedTime")
        effective_raw = entry.get("effectiveTime")
        expire_raw = entry.get("expireTime")
        if not alert_id or not issued_raw or not effective_raw or not expire_raw:
            raise ValueError("Missing required WeatherKit alert fields")

        issued_at = _parse_iso8601(str(issued_raw), iso_parser)
        effective_time = _parse_iso8601(str(effective_raw), iso_parser)
        expire_time = _parse_iso8601(str(expire_raw), iso_parser)
        event_start_raw = entry.get("eventOnsetTime")
        event_end_raw = entry.get("eventEndTime")

        responses = entry.get("responses") or []
        responses_tuple: tuple[str, ...] = tuple(str(item) for item in responses if item is not None)

        normalized.append(
            WeatherAlert(
                provider=provider,
                location=location,
                alert_id=str(alert_id),
                issued_at=issued_at,
                effective_time=effective_time,
                expire_time=expire_time,
                event_start=_parse_iso8601(str(event_start_raw), iso_parser) if event_start_raw else None,
                event_end=_parse_iso8601(str(event_end_raw), iso_parser) if event_end_raw else None,
                severity=str(entry.get("severity")) if entry.get("severity") is not None else None,
                certainty=str(entry.get("certainty")) if entry.get("certainty") is not None else None,
                urgency=str(entry.get("urgency")) if entry.get("urgency") is not None else None,
                responses=responses_tuple,
                description=str(entry.get("description")) if entry.get("description") is not None else None,
                source=str(entry.get("source")) if entry.get("source") is not None else None,
                area_id=str(entry.get("areaId")) if entry.get("areaId") is not None else None,
                area_name=str(entry.get("areaName")) if entry.get("areaName") is not None else None,
                details_url=str(entry.get("detailsUrl")) if entry.get("detailsUrl") is not None else None,
                country_code=str(entry.get("countryCode")) if entry.get("countryCode") is not None else None,
            )
        )

    return normalized
