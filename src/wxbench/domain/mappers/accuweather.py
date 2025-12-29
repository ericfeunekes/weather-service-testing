"""Mapping helpers for AccuWeather payloads."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping, Optional, Sequence

from wxbench.domain.models import ForecastPeriod, Location, Observation


def _to_optional_int(value: Any) -> Optional[int]:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _to_optional_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _fahrenheit_to_celsius(value: Optional[float]) -> Optional[float]:
    if value is None:
        return None
    return (value - 32.0) * 5.0 / 9.0


def _mph_to_kph(value: Optional[float]) -> Optional[float]:
    if value is None:
        return None
    return value * 1.60934


def _miles_to_km(value: Optional[float]) -> Optional[float]:
    if value is None:
        return None
    return value * 1.60934


def _inches_to_mm(value: Optional[float]) -> Optional[float]:
    if value is None:
        return None
    return value * 25.4


def _pressure_to_kpa(value: Optional[float], unit: Optional[str]) -> Optional[float]:
    if value is None:
        return None
    if unit is None:
        return value
    unit_lower = unit.lower()
    if unit_lower in {"kpa"}:
        return value
    if unit_lower in {"mb", "hpa"}:
        return value / 10.0
    if unit_lower in {"inhg"}:
        return value * 3.38639
    return value


def _extract_metric_block(block: Mapping[str, Any]) -> tuple[Optional[float], Optional[str]]:
    if not isinstance(block, Mapping):
        return None, None
    value = _to_optional_float(block.get("Value"))
    unit = block.get("Unit")
    return value, str(unit) if unit else None


def _temperature_from_block(block: Mapping[str, Any]) -> Optional[float]:
    value, unit = _extract_metric_block(block)
    if unit and unit.lower().startswith("f"):
        return _fahrenheit_to_celsius(value)
    return value


def _speed_from_block(block: Mapping[str, Any]) -> Optional[float]:
    value, unit = _extract_metric_block(block)
    if unit and unit.lower() in {"mi/h", "mph"}:
        return _mph_to_kph(value)
    return value


def _distance_from_block(block: Mapping[str, Any]) -> Optional[float]:
    value, unit = _extract_metric_block(block)
    if unit and unit.lower() in {"mi"}:
        return _miles_to_km(value)
    if unit and unit.lower() in {"m"}:
        return value / 1000.0 if value is not None else None
    if unit and unit.lower() in {"ft", "feet"}:
        return value * 0.0003048 if value is not None else None
    return value


def _precip_from_block(block: Mapping[str, Any]) -> Optional[float]:
    value, unit = _extract_metric_block(block)
    if unit and unit.lower() in {"in"}:
        return _inches_to_mm(value)
    return value


def _parse_epoch_seconds(value: Any) -> Optional[datetime]:
    epoch = _to_optional_int(value)
    if epoch is None:
        return None
    return datetime.fromtimestamp(epoch, tz=timezone.utc)


def _parse_iso8601(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    text = str(value)
    if text.endswith("Z"):
        text = text.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def _first_text(*values: Any) -> Optional[str]:
    for value in values:
        if value is None:
            continue
        text = str(value)
        if text.strip():
            return text
    return None


def _interval_summary(interval: Mapping[str, Any], fallback: Mapping[str, Any]) -> Optional[str]:
    return _first_text(
        interval.get("ShortPhrase"),
        interval.get("BriefPhrase"),
        interval.get("LongPhrase"),
        interval.get("MinuteText"),
        interval.get("MinutesText"),
        interval.get("WidgetPhrase"),
        fallback.get("ShortPhrase"),
        fallback.get("BriefPhrase"),
        fallback.get("LongPhrase"),
        fallback.get("MinuteText"),
        fallback.get("MinutesText"),
        fallback.get("Phrase"),
    )


def _interval_bounds(interval: Mapping[str, Any], issued_at: datetime) -> tuple[datetime, datetime]:
    start_minute = _to_optional_int(interval.get("StartMinute"))
    if start_minute is None:
        raise ValueError("Missing interval start minute")

    end_minute = _to_optional_int(interval.get("EndMinute"))
    count_minute = _to_optional_int(interval.get("CountMinute"))

    start_time = issued_at + timedelta(minutes=start_minute)
    if count_minute and count_minute > 0:
        end_time = start_time + timedelta(minutes=count_minute)
    elif end_minute is not None:
        end_time = issued_at + timedelta(minutes=end_minute + 1)
    else:
        end_time = start_time + timedelta(minutes=1)

    return start_time, end_time


def _average_from_range(block: Mapping[str, Any]) -> Optional[float]:
    if not isinstance(block, Mapping):
        return None
    average = block.get("Average")
    if isinstance(average, Mapping):
        return _to_optional_float(average.get("Value") if "Value" in average else average)
    if average is not None:
        return _to_optional_float(average)

    minimum = block.get("Minimum")
    maximum = block.get("Maximum")
    min_val = None
    max_val = None
    if isinstance(minimum, Mapping):
        min_val = _to_optional_float(minimum.get("Value") if "Value" in minimum else minimum)
    else:
        min_val = _to_optional_float(minimum)
    if isinstance(maximum, Mapping):
        max_val = _to_optional_float(maximum.get("Value") if "Value" in maximum else maximum)
    else:
        max_val = _to_optional_float(maximum)
    if min_val is not None and max_val is not None:
        return (min_val + max_val) / 2.0
    return min_val if min_val is not None else max_val


def _average_temperature_from_range(block: Mapping[str, Any]) -> Optional[float]:
    if not isinstance(block, Mapping):
        return None
    average = block.get("Average")
    if isinstance(average, Mapping):
        return _temperature_from_block(average)

    minimum = block.get("Minimum") if isinstance(block.get("Minimum"), Mapping) else None
    maximum = block.get("Maximum") if isinstance(block.get("Maximum"), Mapping) else None
    min_val = _temperature_from_block(minimum) if minimum is not None else None
    max_val = _temperature_from_block(maximum) if maximum is not None else None
    if min_val is not None and max_val is not None:
        return (min_val + max_val) / 2.0
    return min_val if min_val is not None else max_val


def map_accuweather_minute_forecast(
    payload: Mapping[str, Any],
    *,
    latitude: float,
    longitude: float,
    issued_at: datetime,
    provider: str = "accuweather",
) -> list[ForecastPeriod]:
    if latitude is None or longitude is None:
        raise ValueError("Missing coordinates for forecast")

    summaries: Sequence[Mapping[str, Any]] = payload.get("Summaries") or []
    if not summaries:
        raise ValueError("Missing minute summaries")

    summary: Mapping[str, Any] = payload.get("Summary") or {}
    location = Location(latitude=float(latitude), longitude=float(longitude))

    periods: list[ForecastPeriod] = []
    for interval in summaries:
        start_time, end_time = _interval_bounds(interval, issued_at)
        summary_text = _interval_summary(interval, summary)

        periods.append(
            ForecastPeriod(
                provider=provider,
                location=location,
                issued_at=issued_at,
                start_time=start_time,
                end_time=end_time,
                summary=summary_text,
                precipitation_probability=None,
                precipitation_mm=None,
                temperature_c=None,
                temperature_high_c=None,
                temperature_low_c=None,
                wind_speed_kph=None,
                wind_direction_deg=None,
            )
        )

    return periods


@dataclass(frozen=True)
class AccuweatherLocation:
    key: str
    location: Location
    name: Optional[str]


def map_accuweather_location(payload: Mapping[str, Any]) -> AccuweatherLocation:
    key = payload.get("Key")
    geo: Mapping[str, Any] = payload.get("GeoPosition") or {}
    lat = _to_optional_float(geo.get("Latitude"))
    lon = _to_optional_float(geo.get("Longitude"))
    if not key or lat is None or lon is None:
        raise ValueError("Missing location key or coordinates")
    name = _first_text(payload.get("LocalizedName"), payload.get("EnglishName"))
    return AccuweatherLocation(key=str(key), location=Location(latitude=lat, longitude=lon), name=name)


def map_accuweather_observation(
    payload: Sequence[Mapping[str, Any]],
    *,
    latitude: float,
    longitude: float,
    provider: str = "accuweather",
) -> Observation:
    if latitude is None or longitude is None:
        raise ValueError("Missing coordinates for observation")

    if not payload:
        raise ValueError("Missing current conditions payload")

    current = payload[0]
    observed_at = _parse_epoch_seconds(current.get("EpochTime")) or _parse_iso8601(
        current.get("LocalObservationDateTime")
    )
    if observed_at is None:
        raise ValueError("Missing observation time")

    temperature_block = (current.get("Temperature") or {}).get("Metric") or current.get("Temperature") or {}
    dewpoint_block = (current.get("DewPoint") or {}).get("Metric") or current.get("DewPoint") or {}
    pressure_block = (current.get("Pressure") or {}).get("Metric") or current.get("Pressure") or {}
    visibility_block = (current.get("Visibility") or {}).get("Metric") or current.get("Visibility") or {}
    ceiling_block = (current.get("Ceiling") or {}).get("Metric") or current.get("Ceiling") or {}

    wind: Mapping[str, Any] = current.get("Wind") or {}
    wind_speed_block = (wind.get("Speed") or {}).get("Metric") or wind.get("Speed") or {}
    wind_direction = (wind.get("Direction") or {}).get("Degrees")

    gust: Mapping[str, Any] = current.get("WindGust") or {}
    gust_speed_block = (gust.get("Speed") or {}).get("Metric") or gust.get("Speed") or {}
    uv_index = _to_optional_float(current.get("UVIndexFloat") or current.get("UVIndex"))

    real_feel_block = (current.get("RealFeelTemperature") or {}).get("Metric") or current.get("RealFeelTemperature") or {}
    real_feel_shade_block = (current.get("RealFeelTemperatureShade") or {}).get("Metric") or current.get("RealFeelTemperatureShade") or {}
    apparent_block = (current.get("ApparentTemperature") or {}).get("Metric") or current.get("ApparentTemperature") or {}
    wind_chill_block = (current.get("WindChillTemperature") or {}).get("Metric") or current.get("WindChillTemperature") or {}
    wet_bulb_block = (current.get("WetBulbTemperature") or {}).get("Metric") or current.get("WetBulbTemperature") or {}
    wet_bulb_globe_block = (current.get("WetBulbGlobeTemperature") or {}).get("Metric") or current.get("WetBulbGlobeTemperature") or {}
    departure_block = (current.get("Past24HourTemperatureDeparture") or {}).get("Metric") or current.get("Past24HourTemperatureDeparture") or {}

    precipitation_summary = (current.get("PrecipitationSummary") or {}).get("Precipitation") or {}
    precipitation_block = precipitation_summary.get("Metric") or precipitation_summary
    precipitation_one_hour = (current.get("Precip1hr") or {}).get("Metric") or current.get("Precip1hr") or {}
    pressure_tendency = current.get("PressureTendency") or {}

    return Observation(
        provider=provider,
        station=_first_text(current.get("StationName"), current.get("WeatherText")),
        location=Location(latitude=float(latitude), longitude=float(longitude)),
        observed_at=observed_at,
        temperature_c=_temperature_from_block(temperature_block),
        temperature_apparent_c=_temperature_from_block(real_feel_block),
        temperature_apparent_shade_c=_temperature_from_block(real_feel_shade_block),
        temperature_apparent_alt_c=_temperature_from_block(apparent_block),
        temperature_wind_chill_c=_temperature_from_block(wind_chill_block),
        temperature_wet_bulb_c=_temperature_from_block(wet_bulb_block),
        temperature_wet_bulb_globe_c=_temperature_from_block(wet_bulb_globe_block),
        temperature_departure_24h_c=_temperature_from_block(departure_block),
        dewpoint_c=_temperature_from_block(dewpoint_block),
        wind_speed_kph=_speed_from_block(wind_speed_block),
        wind_direction_deg=_to_optional_int(wind_direction),
        wind_gust_kph=_speed_from_block(gust_speed_block),
        pressure_kpa=_pressure_to_kpa(*_extract_metric_block(pressure_block)),
        pressure_sea_level_kpa=_pressure_to_kpa(*_extract_metric_block(pressure_block)),
        relative_humidity=_to_optional_float(current.get("RelativeHumidity")),
        relative_humidity_in=_to_optional_float(current.get("IndoorRelativeHumidity")),
        visibility_km=_distance_from_block(visibility_block),
        cloud_ceiling_km=_distance_from_block(ceiling_block),
        cloud_cover_pct=_to_optional_float(current.get("CloudCover")),
        condition=_first_text(current.get("WeatherText")),
        condition_code=_to_optional_int(current.get("WeatherIcon")),
        precipitation_last_hour_mm=_precip_from_block(precipitation_one_hour) or _precip_from_block(precipitation_block),
        uv_index=uv_index,
        precipitation_type=_first_text(current.get("PrecipitationType")),
        pressure_tendency=_first_text(pressure_tendency.get("LocalizedText"), pressure_tendency.get("Code")),
    )


def map_accuweather_hourly_forecast(
    payload: Sequence[Mapping[str, Any]],
    *,
    latitude: float,
    longitude: float,
    provider: str = "accuweather",
) -> list[ForecastPeriod]:
    if latitude is None or longitude is None:
        raise ValueError("Missing coordinates for forecast")
    if not payload:
        raise ValueError("Missing hourly forecast payload")

    issued_at = _parse_epoch_seconds(payload[0].get("EpochDateTime")) or _parse_iso8601(payload[0].get("DateTime"))
    if issued_at is None:
        raise ValueError("Missing forecast issue time")

    periods: list[ForecastPeriod] = []
    for entry in payload:
        start_time = _parse_epoch_seconds(entry.get("EpochDateTime")) or _parse_iso8601(entry.get("DateTime"))
        if start_time is None:
            raise ValueError("Missing forecast start time")
        end_time = start_time + timedelta(hours=1)

        temp_block = (entry.get("Temperature") or {}).get("Metric") or entry.get("Temperature") or {}
        real_feel_block = (entry.get("RealFeelTemperature") or {}).get("Metric") or entry.get("RealFeelTemperature") or {}
        real_feel_shade_block = (entry.get("RealFeelTemperatureShade") or {}).get("Metric") or entry.get("RealFeelTemperatureShade") or {}
        dewpoint_block = (entry.get("DewPoint") or {}).get("Metric") or entry.get("DewPoint") or {}
        wet_bulb_block = (entry.get("WetBulbTemperature") or {}).get("Metric") or entry.get("WetBulbTemperature") or {}
        wet_bulb_globe_block = (entry.get("WetBulbGlobeTemperature") or {}).get("Metric") or entry.get("WetBulbGlobeTemperature") or {}
        wind: Mapping[str, Any] = entry.get("Wind") or {}
        wind_speed_block = (wind.get("Speed") or {}).get("Metric") or wind.get("Speed") or {}
        wind_direction = (wind.get("Direction") or {}).get("Degrees")
        gust: Mapping[str, Any] = entry.get("WindGust") or {}
        gust_speed_block = (gust.get("Speed") or {}).get("Metric") or gust.get("Speed") or {}
        uv_index = _to_optional_float(entry.get("UVIndexFloat") or entry.get("UVIndex"))
        rain_block = (entry.get("Rain") or {}).get("Metric") or entry.get("Rain") or {}
        snow_block = (entry.get("Snow") or {}).get("Metric") or entry.get("Snow") or {}
        ice_block = (entry.get("Ice") or {}).get("Metric") or entry.get("Ice") or {}
        total_liquid = (entry.get("TotalLiquid") or {}).get("Metric") or entry.get("TotalLiquid") or {}
        visibility_block = (entry.get("Visibility") or {}).get("Metric") or entry.get("Visibility") or {}
        ceiling_block = (entry.get("Ceiling") or {}).get("Metric") or entry.get("Ceiling") or {}

        precip_total = _precip_from_block(total_liquid) or _precip_from_block(rain_block) or _precip_from_block(snow_block)

        periods.append(
            ForecastPeriod(
                provider=provider,
                location=Location(latitude=float(latitude), longitude=float(longitude)),
                issued_at=issued_at,
                start_time=start_time,
                end_time=end_time,
                temperature_c=_temperature_from_block(temp_block),
                temperature_apparent_c=_temperature_from_block(real_feel_block),
                temperature_apparent_shade_c=_temperature_from_block(real_feel_shade_block),
                temperature_wet_bulb_c=_temperature_from_block(wet_bulb_block),
                temperature_wet_bulb_globe_c=_temperature_from_block(wet_bulb_globe_block),
                dewpoint_c=_temperature_from_block(dewpoint_block),
                temperature_high_c=None,
                temperature_low_c=None,
                precipitation_probability=_to_optional_float(entry.get("PrecipitationProbability")),
                precipitation_probability_thunderstorm=_to_optional_float(entry.get("ThunderstormProbability")),
                precipitation_probability_rain=_to_optional_float(entry.get("RainProbability")),
                precipitation_probability_snow=_to_optional_float(entry.get("SnowProbability")),
                precipitation_probability_ice=_to_optional_float(entry.get("IceProbability")),
                precipitation_mm=precip_total,
                precipitation_amount_rain_mm=_precip_from_block(rain_block),
                precipitation_amount_snow_mm=_precip_from_block(snow_block),
                precipitation_amount_ice_mm=_precip_from_block(ice_block),
                summary=_first_text(entry.get("IconPhrase"), entry.get("ShortPhrase"), entry.get("LongPhrase")),
                condition_code=_to_optional_int(entry.get("WeatherIcon")),
                wind_speed_kph=_speed_from_block(wind_speed_block),
                wind_direction_deg=_to_optional_int(wind_direction),
                wind_gust_kph=_speed_from_block(gust_speed_block),
                uv_index=uv_index,
                relative_humidity=_to_optional_float(entry.get("RelativeHumidity")),
                visibility_km=_distance_from_block(visibility_block),
                cloud_ceiling_km=_distance_from_block(ceiling_block),
            )
        )

    return periods


def map_accuweather_daily_forecast(
    payload: Mapping[str, Any],
    *,
    latitude: float,
    longitude: float,
    provider: str = "accuweather",
) -> list[ForecastPeriod]:
    if latitude is None or longitude is None:
        raise ValueError("Missing coordinates for forecast")

    daily: Sequence[Mapping[str, Any]] = payload.get("DailyForecasts") or []
    if not daily:
        raise ValueError("Missing daily forecast payload")

    first_time = _parse_epoch_seconds(daily[0].get("EpochDate")) or _parse_iso8601(daily[0].get("Date"))
    if first_time is None:
        raise ValueError("Missing forecast issue time")
    issued_at = first_time

    periods: list[ForecastPeriod] = []
    for entry in daily:
        start_time = _parse_epoch_seconds(entry.get("EpochDate")) or _parse_iso8601(entry.get("Date"))
        if start_time is None:
            raise ValueError("Missing forecast start time")
        end_time = start_time + timedelta(days=1)

        temp = entry.get("Temperature") or {}
        temp_min_block = (temp.get("Minimum") or {}).get("Metric") or temp.get("Minimum") or {}
        temp_max_block = (temp.get("Maximum") or {}).get("Metric") or temp.get("Maximum") or {}

        day_block: Mapping[str, Any] = entry.get("Day") or {}
        real_feel = entry.get("RealFeelTemperature") or {}
        real_feel_min_block = (real_feel.get("Minimum") or {}).get("Metric") or real_feel.get("Minimum") or {}
        real_feel_max_block = (real_feel.get("Maximum") or {}).get("Metric") or real_feel.get("Maximum") or {}
        real_feel_shade = entry.get("RealFeelTemperatureShade") or {}
        wind: Mapping[str, Any] = day_block.get("Wind") or {}
        wind_speed_block = (wind.get("Speed") or {}).get("Metric") or wind.get("Speed") or {}
        wind_direction = (wind.get("Direction") or {}).get("Degrees")
        gust: Mapping[str, Any] = day_block.get("WindGust") or {}
        gust_speed_block = (gust.get("Speed") or {}).get("Metric") or gust.get("Speed") or {}
        uv_value = day_block.get("UVIndex") or day_block.get("UVIndexFloat")
        uv_index = None
        if isinstance(uv_value, Mapping):
            uv_min = _to_optional_float(uv_value.get("Minimum"))
            uv_max = _to_optional_float(uv_value.get("Maximum"))
            if uv_min is not None and uv_max is not None:
                uv_index = (uv_min + uv_max) / 2.0
            else:
                uv_index = uv_max or uv_min
        else:
            uv_index = _to_optional_float(uv_value)

        rain_block = (day_block.get("Rain") or {}).get("Metric") or day_block.get("Rain") or {}
        snow_block = (day_block.get("Snow") or {}).get("Metric") or day_block.get("Snow") or {}
        ice_block = (day_block.get("Ice") or {}).get("Metric") or day_block.get("Ice") or {}
        total_liquid = (day_block.get("TotalLiquid") or {}).get("Metric") or day_block.get("TotalLiquid") or {}
        precip_total = _precip_from_block(total_liquid) or _precip_from_block(rain_block) or _precip_from_block(snow_block)
        wet_bulb_block = day_block.get("WetBulbTemperature") or {}
        wet_bulb_globe_block = day_block.get("WetBulbGlobeTemperature") or {}
        humidity_block = day_block.get("RelativeHumidity") or {}
        evapotranspiration_block = day_block.get("Evapotranspiration") or {}
        solar_irradiance_block = day_block.get("SolarIrradiance") or {}

        temp_min = _temperature_from_block(temp_min_block)
        temp_max = _temperature_from_block(temp_max_block)
        temp_avg = None
        if temp_min is not None and temp_max is not None:
            temp_avg = (temp_min + temp_max) / 2.0
        real_feel_min = _temperature_from_block(real_feel_min_block)
        real_feel_max = _temperature_from_block(real_feel_max_block)
        temp_apparent = None
        if real_feel_min is not None and real_feel_max is not None:
            temp_apparent = (real_feel_min + real_feel_max) / 2.0
        temp_apparent_shade = _average_temperature_from_range(real_feel_shade)

        periods.append(
            ForecastPeriod(
                provider=provider,
                location=Location(latitude=float(latitude), longitude=float(longitude)),
                issued_at=issued_at,
                start_time=start_time,
                end_time=end_time,
                temperature_c=temp_avg,
                temperature_apparent_c=temp_apparent,
                temperature_apparent_shade_c=temp_apparent_shade,
                temperature_high_c=temp_max,
                temperature_low_c=temp_min,
                precipitation_probability=_to_optional_float(day_block.get("PrecipitationProbability")),
                precipitation_probability_thunderstorm=_to_optional_float(day_block.get("ThunderstormProbability")),
                precipitation_probability_rain=_to_optional_float(day_block.get("RainProbability")),
                precipitation_probability_snow=_to_optional_float(day_block.get("SnowProbability")),
                precipitation_probability_ice=_to_optional_float(day_block.get("IceProbability")),
                precipitation_mm=precip_total,
                precipitation_amount_rain_mm=_precip_from_block(rain_block),
                precipitation_amount_snow_mm=_precip_from_block(snow_block),
                precipitation_amount_ice_mm=_precip_from_block(ice_block),
                summary=_first_text(day_block.get("IconPhrase"), day_block.get("ShortPhrase"), day_block.get("LongPhrase")),
                condition_code=_to_optional_int(day_block.get("Icon")),
                wind_speed_kph=_speed_from_block(wind_speed_block),
                wind_direction_deg=_to_optional_int(wind_direction),
                wind_gust_kph=_speed_from_block(gust_speed_block),
                uv_index=uv_index,
                relative_humidity=_average_from_range(humidity_block),
                cloud_cover_pct=_to_optional_float(day_block.get("CloudCover")),
                evapotranspiration_mm=_precip_from_block(evapotranspiration_block),
                solar_irradiance_wm2=_to_optional_float(_extract_metric_block(solar_irradiance_block)[0]),
                sun_hours=_to_optional_float(entry.get("HoursOfSun")),
                temperature_wet_bulb_c=_average_temperature_from_range(wet_bulb_block),
                temperature_wet_bulb_globe_c=_average_temperature_from_range(wet_bulb_globe_block),
            )
        )

    return periods


__all__ = [
    "AccuweatherLocation",
    "map_accuweather_location",
    "map_accuweather_observation",
    "map_accuweather_hourly_forecast",
    "map_accuweather_daily_forecast",
    "map_accuweather_minute_forecast",
]
