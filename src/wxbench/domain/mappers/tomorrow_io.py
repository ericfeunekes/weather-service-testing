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


def _sum_intensities(values: Mapping[str, Any]) -> Optional[float]:
    total = 0.0
    found = False
    for key in ("rainIntensity", "snowIntensity", "sleetIntensity", "freezingRainIntensity"):
        amount = _to_optional_float(values.get(key))
        if amount is None:
            continue
        total += amount
        found = True
    return total if found else None


def _daily_value(values: Mapping[str, Any], base: str, suffix: str = "Avg") -> Optional[float]:
    for key in (f"{base}{suffix}", base):
        if key in values and values[key] is not None:
            return _to_optional_float(values.get(key))
    return None


def _daily_value_sum(values: Mapping[str, Any], base: str) -> Optional[float]:
    return _daily_value(values, base, "Sum")


def _daily_value_max(values: Mapping[str, Any], base: str) -> Optional[float]:
    return _daily_value(values, base, "Max")


def map_tomorrow_io_observation(
    payload: Mapping[str, Any], *, provider: str = "tomorrow_io", iso_parser: Optional[IsoParser] = None
) -> Observation:
    data: Mapping[str, Any] = payload.get("data") or {}
    values: Mapping[str, Any] = data.get("values") or {}
    location: Mapping[str, Any] = payload.get("location") or {}

    if "lat" not in location or "lon" not in location:
        raise ValueError("Missing coordinates for observation")

    observed_raw = data.get("time")
    if not observed_raw:
        raise ValueError("Missing observation time")

    observed_at = _parse_iso8601(str(observed_raw), iso_parser)

    temperature = _to_optional_float(values.get("temperature"))
    temperature_apparent = _to_optional_float(values.get("temperatureApparent"))
    dewpoint = _to_optional_float(values.get("dewPoint"))
    wind_speed = _ms_to_kph(_to_optional_float(values.get("windSpeed")))
    wind_direction = _to_optional_int(values.get("windDirection"))
    wind_gust = _ms_to_kph(_to_optional_float(values.get("windGust")))
    pressure_surface = _hpa_to_kpa(_to_optional_float(values.get("pressureSurfaceLevel")))
    pressure_sea_level = _hpa_to_kpa(_to_optional_float(values.get("pressureSeaLevel")))
    altimeter = _hpa_to_kpa(_to_optional_float(values.get("altimeterSetting")))
    humidity = _to_optional_float(values.get("humidity"))
    visibility = _to_optional_float(values.get("visibility"))
    uv_index = _to_optional_float(values.get("uvIndex"))
    uv_health = _to_optional_float(values.get("uvHealthConcern"))
    condition = _describe_weather_code(values.get("weatherCode"))
    condition_code = _to_optional_int(values.get("weatherCode"))
    precipitation_hour = _sum_intensities(values)
    cloud_cover = _to_optional_float(values.get("cloudCover"))
    cloud_base = _to_optional_float(values.get("cloudBase"))
    cloud_ceiling = _to_optional_float(values.get("cloudCeiling"))
    rain_intensity = _to_optional_float(values.get("rainIntensity"))
    snow_intensity = _to_optional_float(values.get("snowIntensity"))
    sleet_intensity = _to_optional_float(values.get("sleetIntensity"))
    freezing_rain_intensity = _to_optional_float(values.get("freezingRainIntensity"))

    return Observation(
        provider=provider,
        station=location.get("name"),
        location=Location(latitude=float(location["lat"]), longitude=float(location["lon"])),
        observed_at=observed_at,
        temperature_c=temperature,
        temperature_apparent_c=temperature_apparent,
        dewpoint_c=dewpoint,
        wind_speed_kph=wind_speed,
        wind_direction_deg=wind_direction,
        wind_gust_kph=wind_gust,
        pressure_kpa=pressure_surface,
        pressure_surface_kpa=pressure_surface,
        pressure_sea_level_kpa=pressure_sea_level,
        altimeter_kpa=altimeter,
        relative_humidity=humidity,
        visibility_km=visibility,
        cloud_cover_pct=cloud_cover,
        cloud_base_km=cloud_base,
        cloud_ceiling_km=cloud_ceiling,
        condition=condition,
        condition_code=condition_code,
        precipitation_last_hour_mm=precipitation_hour,
        precipitation_rate_rain_mm_hr=rain_intensity,
        precipitation_rate_snow_mm_hr=snow_intensity,
        precipitation_rate_sleet_mm_hr=sleet_intensity,
        precipitation_rate_freezing_rain_mm_hr=freezing_rain_intensity,
        uv_index=uv_index,
        uv_health_concern=uv_health,
    )


def _infer_end_time(
    index: int,
    intervals: Sequence[Mapping[str, Any]],
    start_time: datetime,
    timestep: Optional[str],
    iso_parser: Optional[IsoParser],
) -> datetime:
    if index + 1 < len(intervals):
        next_raw = intervals[index + 1].get("time")
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
    if timestep and timestep.endswith("d"):
        days = _to_optional_float(timestep[:-1])
        if days:
            return start_time + timedelta(days=days)

    return start_time


def _first_present(values: Mapping[str, Any], keys: Iterable[str]) -> Optional[float]:
    for key in keys:
        if key in values:
            candidate = _to_optional_float(values.get(key))
            if candidate is not None:
                return candidate
    return None


def map_tomorrow_io_forecast(
    payload: Mapping[str, Any], *, provider: str = "tomorrow_io", iso_parser: Optional[IsoParser] = None
) -> list[ForecastPeriod]:
    location: Mapping[str, Any] = payload.get("location") or {}
    timelines: Mapping[str, Any] = payload.get("timelines") or {}
    intervals: Sequence[Mapping[str, Any]] = timelines.get("hourly") or []

    if "lat" not in location or "lon" not in location:
        raise ValueError("Missing coordinates for forecast")

    if not intervals:
        return []

    issued_raw = intervals[0].get("time")
    if not issued_raw:
        raise ValueError("Missing forecast issue time")
    issued_at = _parse_iso8601(str(issued_raw), iso_parser)

    normalized: list[ForecastPeriod] = []
    for index, interval in enumerate(intervals):
        start_raw = interval.get("time")
        if not start_raw:
            raise ValueError("Forecast interval missing start time")

        start_time = _parse_iso8601(str(start_raw), iso_parser)
        end_time = _infer_end_time(index, intervals, start_time, "1h", iso_parser)

        values: Mapping[str, Any] = interval.get("values") or {}
        temp = _to_optional_float(values.get("temperature"))
        temp_apparent = _to_optional_float(values.get("temperatureApparent"))
        dewpoint = _to_optional_float(values.get("dewPoint"))
        pop = _to_optional_float(values.get("precipitationProbability"))
        precip_intensity = _sum_intensities(values)
        rain_intensity = _to_optional_float(values.get("rainIntensity"))
        snow_intensity = _to_optional_float(values.get("snowIntensity"))
        sleet_intensity = _to_optional_float(values.get("sleetIntensity"))
        freezing_rain_intensity = _to_optional_float(values.get("freezingRainIntensity"))
        wind_speed = _ms_to_kph(_to_optional_float(values.get("windSpeed")))
        wind_dir = _to_optional_int(values.get("windDirection"))
        wind_gust = _ms_to_kph(_to_optional_float(values.get("windGust")))
        uv_index = _to_optional_float(values.get("uvIndex"))
        uv_health = _to_optional_float(values.get("uvHealthConcern"))
        humidity = _to_optional_float(values.get("humidity"))
        visibility = _to_optional_float(values.get("visibility"))
        pressure_surface = _hpa_to_kpa(_to_optional_float(values.get("pressureSurfaceLevel")))
        pressure_sea_level = _hpa_to_kpa(_to_optional_float(values.get("pressureSeaLevel")))
        altimeter = _hpa_to_kpa(_to_optional_float(values.get("altimeterSetting")))
        cloud_cover = _to_optional_float(values.get("cloudCover"))
        cloud_base = _to_optional_float(values.get("cloudBase"))
        cloud_ceiling = _to_optional_float(values.get("cloudCeiling"))
        rain_accum = _to_optional_float(values.get("rainAccumulation"))
        snow_accum = _to_optional_float(values.get("snowAccumulation"))
        sleet_accum = _to_optional_float(values.get("sleetAccumulation"))
        ice_accum = _to_optional_float(values.get("iceAccumulation"))
        snow_lwe = _to_optional_float(values.get("snowAccumulationLwe"))
        sleet_lwe = _to_optional_float(values.get("sleetAccumulationLwe"))
        ice_lwe = _to_optional_float(values.get("iceAccumulationLwe"))
        snow_depth = _to_optional_float(values.get("snowDepth"))
        evapotranspiration = _to_optional_float(values.get("evapotranspiration"))
        condition_code = _to_optional_int(values.get("weatherCode"))
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
                temperature_apparent_c=temp_apparent,
                dewpoint_c=dewpoint,
                precipitation_probability=pop,
                precipitation_mm=precipitation_mm,
                precipitation_amount_rain_mm=rain_accum,
                precipitation_amount_snow_mm=snow_accum,
                precipitation_amount_sleet_mm=sleet_accum,
                precipitation_amount_ice_mm=ice_accum,
                precipitation_amount_snow_lwe_mm=snow_lwe,
                precipitation_amount_sleet_lwe_mm=sleet_lwe,
                precipitation_amount_ice_lwe_mm=ice_lwe,
                precipitation_rate_rain_mm_hr=rain_intensity,
                precipitation_rate_snow_mm_hr=snow_intensity,
                precipitation_rate_sleet_mm_hr=sleet_intensity,
                precipitation_rate_freezing_rain_mm_hr=freezing_rain_intensity,
                summary=condition,
                condition_code=condition_code,
                wind_speed_kph=wind_speed,
                wind_direction_deg=wind_dir,
                wind_gust_kph=wind_gust,
                uv_index=uv_index,
                uv_health_concern=uv_health,
                relative_humidity=humidity,
                visibility_km=visibility,
                pressure_surface_kpa=pressure_surface,
                pressure_sea_level_kpa=pressure_sea_level,
                altimeter_kpa=altimeter,
                cloud_cover_pct=cloud_cover,
                cloud_base_km=cloud_base,
                cloud_ceiling_km=cloud_ceiling,
                snow_depth_cm=snow_depth,
                evapotranspiration_mm=evapotranspiration,
            )
        )

    return normalized


def map_tomorrow_io_daily_forecast(
    payload: Mapping[str, Any], *, provider: str = "tomorrow_io", iso_parser: Optional[IsoParser] = None
) -> list[ForecastPeriod]:
    location: Mapping[str, Any] = payload.get("location") or {}
    timelines: Mapping[str, Any] = payload.get("timelines") or {}
    intervals: Sequence[Mapping[str, Any]] = timelines.get("daily") or []

    if "lat" not in location or "lon" not in location:
        raise ValueError("Missing coordinates for forecast")

    if not intervals:
        return []

    issued_raw = intervals[0].get("time")
    if not issued_raw:
        raise ValueError("Missing forecast issue time")
    issued_at = _parse_iso8601(str(issued_raw), iso_parser)

    normalized: list[ForecastPeriod] = []
    for index, interval in enumerate(intervals):
        start_raw = interval.get("time")
        if not start_raw:
            raise ValueError("Forecast interval missing start time")

        start_time = _parse_iso8601(str(start_raw), iso_parser)
        end_time = _infer_end_time(index, intervals, start_time, "1d", iso_parser)

        values: Mapping[str, Any] = interval.get("values") or {}
        temp = _first_present(values, ("temperatureAvg", "temperature", "temperatureApparentAvg"))
        temp_high = _first_present(values, ("temperatureMax", "temperatureApparentMax"))
        temp_low = _first_present(values, ("temperatureMin", "temperatureApparentMin"))
        temp_apparent = _first_present(values, ("temperatureApparentAvg", "temperatureApparent"))
        dewpoint = _daily_value(values, "dewPoint")
        humidity = _daily_value(values, "humidity")
        visibility = _daily_value(values, "visibility")
        cloud_cover = _daily_value(values, "cloudCover")
        cloud_base = _daily_value(values, "cloudBase")
        cloud_ceiling = _daily_value(values, "cloudCeiling")
        pressure_sea = _hpa_to_kpa(_daily_value(values, "pressureSeaLevel"))
        pressure_surface = _hpa_to_kpa(_daily_value(values, "pressureSurfaceLevel"))
        altimeter = _hpa_to_kpa(_daily_value(values, "altimeterSetting"))
        pop = _daily_value_max(values, "precipitationProbability") or _daily_value(values, "precipitationProbability")
        rain_sum = _daily_value_sum(values, "rainAccumulation")
        snow_sum = _daily_value_sum(values, "snowAccumulation")
        sleet_sum = _daily_value_sum(values, "sleetAccumulation")
        ice_sum = _daily_value_sum(values, "iceAccumulation")
        snow_lwe_sum = _daily_value_sum(values, "snowAccumulationLwe")
        sleet_lwe_sum = _daily_value_sum(values, "sleetAccumulationLwe")
        ice_lwe_sum = _daily_value_sum(values, "iceAccumulationLwe")
        rain_intensity = _daily_value(values, "rainIntensity")
        snow_intensity = _daily_value(values, "snowIntensity")
        sleet_intensity = _daily_value(values, "sleetIntensity")
        freezing_rain_intensity = _daily_value(values, "freezingRainIntensity")
        snow_depth = _daily_value(values, "snowDepth")
        evapotranspiration = _daily_value_sum(values, "evapotranspiration") or _daily_value(values, "evapotranspiration")
        wind_speed = _ms_to_kph(_first_present(values, ("windSpeedAvg", "windSpeed")))
        wind_dir = _to_optional_int(values.get("windDirectionAvg") or values.get("windDirection"))
        wind_gust = _ms_to_kph(_first_present(values, ("windGustAvg", "windGust")))
        uv_index = _first_present(values, ("uvIndexMax", "uvIndex"))
        uv_health = _first_present(values, ("uvHealthConcernMax", "uvHealthConcernAvg", "uvHealthConcern"))
        condition_code = _to_optional_int(values.get("weatherCodeMax") or values.get("weatherCode"))
        condition = _describe_weather_code(values.get("weatherCode"))

        precip_total = sum(
            value for value in (rain_sum, snow_sum, sleet_sum, ice_sum) if value is not None
        )
        if precip_total == 0:
            precip_total = None

        normalized.append(
            ForecastPeriod(
                provider=provider,
                location=Location(latitude=float(location["lat"]), longitude=float(location["lon"])),
                issued_at=issued_at,
                start_time=start_time,
                end_time=end_time,
                temperature_c=temp,
                temperature_apparent_c=temp_apparent,
                temperature_high_c=temp_high,
                temperature_low_c=temp_low,
                dewpoint_c=dewpoint,
                precipitation_probability=pop,
                precipitation_mm=precip_total,
                precipitation_amount_rain_mm=rain_sum,
                precipitation_amount_snow_mm=snow_sum,
                precipitation_amount_sleet_mm=sleet_sum,
                precipitation_amount_ice_mm=ice_sum,
                precipitation_amount_snow_lwe_mm=snow_lwe_sum,
                precipitation_amount_sleet_lwe_mm=sleet_lwe_sum,
                precipitation_amount_ice_lwe_mm=ice_lwe_sum,
                precipitation_rate_rain_mm_hr=rain_intensity,
                precipitation_rate_snow_mm_hr=snow_intensity,
                precipitation_rate_sleet_mm_hr=sleet_intensity,
                precipitation_rate_freezing_rain_mm_hr=freezing_rain_intensity,
                summary=condition,
                condition_code=condition_code,
                wind_speed_kph=wind_speed,
                wind_direction_deg=wind_dir,
                wind_gust_kph=wind_gust,
                uv_index=uv_index,
                uv_health_concern=_to_optional_float(uv_health),
                relative_humidity=humidity,
                visibility_km=visibility,
                pressure_sea_level_kpa=pressure_sea,
                pressure_surface_kpa=pressure_surface,
                altimeter_kpa=altimeter,
                cloud_cover_pct=cloud_cover,
                cloud_base_km=cloud_base,
                cloud_ceiling_km=cloud_ceiling,
                snow_depth_cm=snow_depth,
                evapotranspiration_mm=evapotranspiration,
            )
        )

    return normalized


__all__ = ["map_tomorrow_io_observation", "map_tomorrow_io_forecast", "map_tomorrow_io_daily_forecast"]
