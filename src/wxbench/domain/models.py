"""Typed domain models for normalized weather data."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Optional


@dataclass(frozen=True)
class Location:
    """Geographic point for a station or grid cell."""

    latitude: float
    longitude: float


@dataclass(frozen=True)
class Observation:
    """Normalized observation emitted by a provider."""

    provider: str
    station: Optional[str]
    location: Location
    observed_at: datetime
    temperature_c: Optional[float] = None
    dewpoint_c: Optional[float] = None
    wind_speed_kph: Optional[float] = None
    wind_direction_deg: Optional[int] = None
    pressure_kpa: Optional[float] = None
    relative_humidity: Optional[float] = None
    visibility_km: Optional[float] = None
    condition: Optional[str] = None
    precipitation_last_hour_mm: Optional[float] = None
    precipitation_daily_mm: Optional[float] = None
    precipitation_weekly_mm: Optional[float] = None
    precipitation_monthly_mm: Optional[float] = None
    precipitation_yearly_mm: Optional[float] = None
    precipitation_event_mm: Optional[float] = None
    pressure_absolute_kpa: Optional[float] = None
    wind_gust_kph: Optional[float] = None
    wind_gust_daily_max_kph: Optional[float] = None
    wind_direction_avg_10m_deg: Optional[int] = None
    uv_index: Optional[float] = None
    solar_radiation_wm2: Optional[float] = None
    temperature_apparent_c: Optional[float] = None
    temperature_in_c: Optional[float] = None
    temperature_apparent_in_c: Optional[float] = None
    dewpoint_in_c: Optional[float] = None
    relative_humidity_in: Optional[float] = None
    pressure_sea_level_kpa: Optional[float] = None
    pressure_surface_kpa: Optional[float] = None
    altimeter_kpa: Optional[float] = None
    cloud_cover_pct: Optional[float] = None
    cloud_base_km: Optional[float] = None
    cloud_ceiling_km: Optional[float] = None
    uv_health_concern: Optional[float] = None
    temperature_apparent_shade_c: Optional[float] = None
    temperature_apparent_alt_c: Optional[float] = None
    temperature_wind_chill_c: Optional[float] = None
    temperature_wet_bulb_c: Optional[float] = None
    temperature_wet_bulb_globe_c: Optional[float] = None
    temperature_departure_24h_c: Optional[float] = None
    precipitation_type: Optional[str] = None
    pressure_tendency: Optional[str] = None
    condition_code: Optional[int] = None
    precipitation_rate_rain_mm_hr: Optional[float] = None
    precipitation_rate_snow_mm_hr: Optional[float] = None
    precipitation_rate_sleet_mm_hr: Optional[float] = None
    precipitation_rate_freezing_rain_mm_hr: Optional[float] = None
    precipitation_rate_ice_mm_hr: Optional[float] = None
    battery_in: Optional[float] = None
    battery_out: Optional[float] = None


@dataclass(frozen=True)
class ForecastPeriod:
    """Normalized forecast period from a provider."""

    provider: str
    location: Location
    issued_at: datetime
    start_time: datetime
    end_time: datetime
    temperature_c: Optional[float] = None
    dewpoint_c: Optional[float] = None
    temperature_high_c: Optional[float] = None
    temperature_low_c: Optional[float] = None
    precipitation_probability: Optional[float] = None
    precipitation_mm: Optional[float] = None
    summary: Optional[str] = None
    wind_speed_kph: Optional[float] = None
    wind_direction_deg: Optional[int] = None
    wind_gust_kph: Optional[float] = None
    temperature_apparent_c: Optional[float] = None
    uv_index: Optional[float] = None
    relative_humidity: Optional[float] = None
    visibility_km: Optional[float] = None
    pressure_sea_level_kpa: Optional[float] = None
    pressure_surface_kpa: Optional[float] = None
    altimeter_kpa: Optional[float] = None
    cloud_cover_pct: Optional[float] = None
    cloud_base_km: Optional[float] = None
    cloud_ceiling_km: Optional[float] = None
    uv_health_concern: Optional[float] = None
    temperature_apparent_shade_c: Optional[float] = None
    temperature_apparent_alt_c: Optional[float] = None
    temperature_wind_chill_c: Optional[float] = None
    temperature_wet_bulb_c: Optional[float] = None
    temperature_wet_bulb_globe_c: Optional[float] = None
    precipitation_probability_rain: Optional[float] = None
    precipitation_probability_snow: Optional[float] = None
    precipitation_probability_ice: Optional[float] = None
    precipitation_probability_thunderstorm: Optional[float] = None
    precipitation_amount_rain_mm: Optional[float] = None
    precipitation_amount_snow_mm: Optional[float] = None
    precipitation_amount_sleet_mm: Optional[float] = None
    precipitation_amount_ice_mm: Optional[float] = None
    precipitation_amount_snow_lwe_mm: Optional[float] = None
    precipitation_amount_sleet_lwe_mm: Optional[float] = None
    precipitation_amount_ice_lwe_mm: Optional[float] = None
    precipitation_rate_rain_mm_hr: Optional[float] = None
    precipitation_rate_snow_mm_hr: Optional[float] = None
    precipitation_rate_sleet_mm_hr: Optional[float] = None
    precipitation_rate_freezing_rain_mm_hr: Optional[float] = None
    precipitation_rate_ice_mm_hr: Optional[float] = None
    snow_depth_cm: Optional[float] = None
    evapotranspiration_mm: Optional[float] = None
    solar_irradiance_wm2: Optional[float] = None
    sun_hours: Optional[float] = None
    condition_code: Optional[int] = None


@dataclass(frozen=True)
class DataPoint:
    """Single normalized metric reading from a provider."""

    provider: str
    product_kind: str
    metric_type: str
    value_num: Optional[float]
    value_text: Optional[str]
    unit: Optional[str]
    value_raw: Optional[str]
    unit_raw: Optional[str]
    observed_at: Optional[datetime]
    valid_start: Optional[datetime]
    valid_end: Optional[datetime]
    issued_at: Optional[datetime]
    run_at: datetime
    local_day: Optional[date]
    lead_unit: Optional[str]
    lead_offset: Optional[int]
    lead_label: Optional[str]
    latitude: float
    longitude: float
    station: Optional[str]
    source_field: Optional[str]
    quality_flag: Optional[str]
