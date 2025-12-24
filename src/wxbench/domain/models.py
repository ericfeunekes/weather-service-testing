"""Typed domain models for normalized weather data."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
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


@dataclass(frozen=True)
class ForecastPeriod:
    """Normalized forecast period from a provider."""

    provider: str
    location: Location
    issued_at: datetime
    start_time: datetime
    end_time: datetime
    temperature_c: Optional[float] = None
    temperature_high_c: Optional[float] = None
    temperature_low_c: Optional[float] = None
    precipitation_probability: Optional[float] = None
    precipitation_mm: Optional[float] = None
    summary: Optional[str] = None
    wind_speed_kph: Optional[float] = None
    wind_direction_deg: Optional[int] = None
