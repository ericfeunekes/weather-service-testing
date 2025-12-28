"""Normalize observations and forecasts into single metric data points."""
from __future__ import annotations

from datetime import date, datetime
from typing import Iterable, Mapping, Optional
from zoneinfo import ZoneInfo

from wxbench.domain.models import DataPoint, ForecastPeriod, Observation


PRODUCT_OBSERVATION = "observation"
PRODUCT_FORECAST_HOURLY = "forecast_hourly"
PRODUCT_FORECAST_DAILY = "forecast_daily"


_OBSERVATION_METRICS: tuple[tuple[str, str, Optional[str], bool], ...] = (
    ("temperature_c", "temperature_air", "C", False),
    ("temperature_apparent_c", "temperature_apparent", "C", False),
    ("temperature_apparent_shade_c", "temperature_apparent_shade", "C", False),
    ("temperature_apparent_alt_c", "temperature_apparent_alt", "C", False),
    ("temperature_wind_chill_c", "temperature_wind_chill", "C", False),
    ("temperature_wet_bulb_c", "temperature_wet_bulb", "C", False),
    ("temperature_wet_bulb_globe_c", "temperature_wet_bulb_globe", "C", False),
    ("temperature_departure_24h_c", "temperature_departure_24h", "C", False),
    ("dewpoint_c", "dewpoint", "C", False),
    ("temperature_in_c", "temperature_indoor", "C", False),
    ("temperature_apparent_in_c", "temperature_apparent_indoor", "C", False),
    ("dewpoint_in_c", "dewpoint_indoor", "C", False),
    ("wind_speed_kph", "wind_speed", "kph", False),
    ("wind_direction_deg", "wind_direction", "deg", False),
    ("wind_gust_kph", "wind_gust", "kph", False),
    ("wind_gust_daily_max_kph", "wind_gust_daily_max", "kph", False),
    ("wind_direction_avg_10m_deg", "wind_direction_avg_10m", "deg", False),
    ("pressure_kpa", "pressure", "kPa", False),
    ("pressure_absolute_kpa", "pressure_absolute", "kPa", False),
    ("pressure_sea_level_kpa", "pressure_sea_level", "kPa", False),
    ("pressure_surface_kpa", "pressure_surface", "kPa", False),
    ("altimeter_kpa", "altimeter", "kPa", False),
    ("relative_humidity", "humidity", "%", False),
    ("relative_humidity_in", "humidity_indoor", "%", False),
    ("visibility_km", "visibility", "km", False),
    ("cloud_cover_pct", "cloud_cover", "%", False),
    ("cloud_base_km", "cloud_base", "km", False),
    ("cloud_ceiling_km", "cloud_ceiling", "km", False),
    ("precipitation_last_hour_mm", "precip_amount", "mm", False),
    ("precipitation_daily_mm", "precip_total_day", "mm", False),
    ("precipitation_weekly_mm", "precip_total_week", "mm", False),
    ("precipitation_monthly_mm", "precip_total_month", "mm", False),
    ("precipitation_yearly_mm", "precip_total_year", "mm", False),
    ("precipitation_event_mm", "precip_total_event", "mm", False),
    ("precipitation_rate_rain_mm_hr", "precip_rate_rain", "mm/hr", False),
    ("precipitation_rate_snow_mm_hr", "precip_rate_snow", "mm/hr", False),
    ("precipitation_rate_sleet_mm_hr", "precip_rate_sleet", "mm/hr", False),
    ("precipitation_rate_freezing_rain_mm_hr", "precip_rate_freezing_rain", "mm/hr", False),
    ("precipitation_rate_ice_mm_hr", "precip_rate_ice", "mm/hr", False),
    ("uv_index", "uv_index", None, False),
    ("uv_health_concern", "uv_health_concern", None, False),
    ("solar_radiation_wm2", "solar_radiation", "W/m2", False),
    ("battery_in", "battery_in", None, False),
    ("battery_out", "battery_out", None, False),
    ("condition", "condition", None, True),
    ("precipitation_type", "precip_type", None, True),
    ("pressure_tendency", "pressure_tendency", None, True),
    ("condition_code", "condition_code", None, False),
)

_FORECAST_METRICS: tuple[tuple[str, str, Optional[str], bool], ...] = (
    ("temperature_c", "temperature_air", "C", False),
    ("dewpoint_c", "dewpoint", "C", False),
    ("temperature_apparent_c", "temperature_apparent", "C", False),
    ("temperature_apparent_shade_c", "temperature_apparent_shade", "C", False),
    ("temperature_apparent_alt_c", "temperature_apparent_alt", "C", False),
    ("temperature_wind_chill_c", "temperature_wind_chill", "C", False),
    ("temperature_wet_bulb_c", "temperature_wet_bulb", "C", False),
    ("temperature_wet_bulb_globe_c", "temperature_wet_bulb_globe", "C", False),
    ("temperature_high_c", "temperature_high", "C", False),
    ("temperature_low_c", "temperature_low", "C", False),
    ("precipitation_probability", "precip_probability", "%", False),
    ("precipitation_probability_rain", "precip_probability_rain", "%", False),
    ("precipitation_probability_snow", "precip_probability_snow", "%", False),
    ("precipitation_probability_ice", "precip_probability_ice", "%", False),
    ("precipitation_probability_thunderstorm", "precip_probability_thunderstorm", "%", False),
    ("precipitation_mm", "precip_amount", "mm", False),
    ("precipitation_amount_rain_mm", "precip_amount_rain", "mm", False),
    ("precipitation_amount_snow_mm", "precip_amount_snow", "mm", False),
    ("precipitation_amount_sleet_mm", "precip_amount_sleet", "mm", False),
    ("precipitation_amount_ice_mm", "precip_amount_ice", "mm", False),
    ("precipitation_amount_snow_lwe_mm", "precip_amount_snow_lwe", "mm", False),
    ("precipitation_amount_sleet_lwe_mm", "precip_amount_sleet_lwe", "mm", False),
    ("precipitation_amount_ice_lwe_mm", "precip_amount_ice_lwe", "mm", False),
    ("precipitation_rate_rain_mm_hr", "precip_rate_rain", "mm/hr", False),
    ("precipitation_rate_snow_mm_hr", "precip_rate_snow", "mm/hr", False),
    ("precipitation_rate_sleet_mm_hr", "precip_rate_sleet", "mm/hr", False),
    ("precipitation_rate_freezing_rain_mm_hr", "precip_rate_freezing_rain", "mm/hr", False),
    ("precipitation_rate_ice_mm_hr", "precip_rate_ice", "mm/hr", False),
    ("snow_depth_cm", "snow_depth", "cm", False),
    ("evapotranspiration_mm", "evapotranspiration", "mm", False),
    ("solar_irradiance_wm2", "solar_irradiance", "W/m2", False),
    ("sun_hours", "sun_hours", "hour", False),
    ("wind_speed_kph", "wind_speed", "kph", False),
    ("wind_direction_deg", "wind_direction", "deg", False),
    ("wind_gust_kph", "wind_gust", "kph", False),
    ("uv_index", "uv_index", None, False),
    ("uv_health_concern", "uv_health_concern", None, False),
    ("relative_humidity", "humidity", "%", False),
    ("visibility_km", "visibility", "km", False),
    ("pressure_sea_level_kpa", "pressure_sea_level", "kPa", False),
    ("pressure_surface_kpa", "pressure_surface", "kPa", False),
    ("altimeter_kpa", "altimeter", "kPa", False),
    ("cloud_cover_pct", "cloud_cover", "%", False),
    ("cloud_base_km", "cloud_base", "km", False),
    ("cloud_ceiling_km", "cloud_ceiling", "km", False),
    ("summary", "condition", None, True),
    ("condition_code", "condition_code", None, False),
)


def _lead_label(offset: int, unit: str) -> str:
    sign = "+" if offset >= 0 else ""
    suffix = "h" if unit == "hour" else "d"
    return f"{sign}{offset}{suffix}"


def _local_day(value: datetime, tz_name: str) -> date:
    return value.astimezone(ZoneInfo(tz_name)).date()


def observation_to_datapoints(
    observation: Observation,
    *,
    run_at: datetime,
    tz_name: str,
    source_fields: Optional[Mapping[str, str]] = None,
) -> list[DataPoint]:
    """Explode a normalized observation into data points."""

    points: list[DataPoint] = []
    for field_name, metric_type, unit, is_text in _OBSERVATION_METRICS:
        value = getattr(observation, field_name)
        if value is None:
            continue
        value_num: Optional[float] = None
        value_text: Optional[str] = None
        if is_text:
            value_text = str(value)
        else:
            value_num = float(value)

        points.append(
            DataPoint(
                provider=observation.provider,
                product_kind=PRODUCT_OBSERVATION,
                metric_type=metric_type,
                value_num=value_num,
                value_text=value_text,
                unit=unit,
                value_raw=None,
                unit_raw=None,
                observed_at=observation.observed_at,
                valid_start=None,
                valid_end=None,
                issued_at=None,
                run_at=run_at,
                local_day=_local_day(observation.observed_at, tz_name),
                lead_unit=None,
                lead_offset=None,
                lead_label=None,
                latitude=observation.location.latitude,
                longitude=observation.location.longitude,
                station=observation.station,
                source_field=(source_fields or {}).get(field_name),
                quality_flag=None,
            )
        )

    return points


def forecast_to_datapoints(
    forecast: ForecastPeriod,
    *,
    run_at: datetime,
    tz_name: str,
    product_kind: str,
    source_fields: Optional[Mapping[str, str]] = None,
    quality_flag: Optional[str] = None,
) -> list[DataPoint]:
    """Explode a normalized forecast period into data points."""

    if product_kind not in (PRODUCT_FORECAST_HOURLY, PRODUCT_FORECAST_DAILY):
        raise ValueError(f"Unsupported product_kind: {product_kind}")

    lead_unit = "hour" if product_kind == PRODUCT_FORECAST_HOURLY else "day"
    if lead_unit == "hour":
        run_hour = run_at.replace(minute=0, second=0, microsecond=0)
        forecast_hour = forecast.start_time.replace(minute=0, second=0, microsecond=0)
        delta = forecast_hour - run_hour
        lead_offset = int(delta.total_seconds() // 3600)
    else:
        forecast_day = _local_day(forecast.start_time, tz_name)
        run_day = _local_day(run_at, tz_name)
        lead_offset = (forecast_day - run_day).days

    lead_label = _lead_label(lead_offset, lead_unit)
    local_day = _local_day(forecast.start_time, tz_name)

    points: list[DataPoint] = []
    for field_name, metric_type, unit, is_text in _FORECAST_METRICS:
        value = getattr(forecast, field_name)
        if value is None:
            continue
        value_num: Optional[float] = None
        value_text: Optional[str] = None
        if is_text:
            value_text = str(value)
        else:
            value_num = float(value)

        points.append(
            DataPoint(
                provider=forecast.provider,
                product_kind=product_kind,
                metric_type=metric_type,
                value_num=value_num,
                value_text=value_text,
                unit=unit,
                value_raw=None,
                unit_raw=None,
                observed_at=None,
                valid_start=forecast.start_time,
                valid_end=forecast.end_time,
                issued_at=forecast.issued_at,
                run_at=run_at,
                local_day=local_day if product_kind == PRODUCT_FORECAST_DAILY else None,
                lead_unit=lead_unit,
                lead_offset=lead_offset,
                lead_label=lead_label,
                latitude=forecast.location.latitude,
                longitude=forecast.location.longitude,
                station=None,
                source_field=(source_fields or {}).get(field_name),
                quality_flag=quality_flag,
            )
        )

    return points


__all__ = [
    "DataPoint",
    "PRODUCT_OBSERVATION",
    "PRODUCT_FORECAST_HOURLY",
    "PRODUCT_FORECAST_DAILY",
    "observation_to_datapoints",
    "forecast_to_datapoints",
]
