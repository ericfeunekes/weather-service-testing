"""Mapping helpers for EcoWitt Cloud payloads."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping, Optional

from wxbench.domain.mappers._common import (
    INCH_TO_MM,
    INHG_TO_KPA,
    MPH_TO_KPH,
    MPS_TO_KPH,
    _to_optional_float,
)
from wxbench.domain.models import Location, Observation


def _to_optional_int(value: Any) -> Optional[int]:
    if value is None:
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _f_to_c(value_f: float) -> float:
    return (value_f - 32.0) * 5.0 / 9.0


def _normalize_temperature_c(value: Any, unit: Any) -> Optional[float]:
    numeric = _to_optional_float(value)
    if numeric is None:
        return None
    unit_str = (str(unit) if unit is not None else "").strip()
    if unit_str in ("°C", "C", "c", "degC"):
        return numeric
    if unit_str in ("°F", "F", "f", "degF"):
        return _f_to_c(numeric)
    # Unknown unit: assume Celsius (cloud APIs commonly return metric by account settings).
    return numeric


def _normalize_wind_kph(value: Any, unit: Any) -> Optional[float]:
    numeric = _to_optional_float(value)
    if numeric is None:
        return None
    unit_str = (str(unit) if unit is not None else "").strip().lower()
    if unit_str in ("km/h", "kph"):
        return numeric
    if unit_str in ("m/s", "ms", "mps"):
        return numeric * MPS_TO_KPH
    if unit_str in ("mph",):
        return numeric * MPH_TO_KPH
    return numeric


def _normalize_pressure_kpa(value: Any, unit: Any) -> Optional[float]:
    numeric = _to_optional_float(value)
    if numeric is None:
        return None
    unit_str = (str(unit) if unit is not None else "").strip().lower()
    if unit_str in ("kpa",):
        return numeric
    if unit_str in ("hpa", "mbar"):
        return numeric / 10.0
    if unit_str in ("inhg", "in hg", "in"):
        return numeric * INHG_TO_KPA
    return numeric


def _normalize_precip_mm(value: Any, unit: Any) -> Optional[float]:
    numeric = _to_optional_float(value)
    if numeric is None:
        return None
    unit_str = (str(unit) if unit is not None else "").strip().lower()
    if unit_str in ("mm",):
        return numeric
    if unit_str in ("in", "inch", "inches"):
        return numeric * INCH_TO_MM
    return numeric


def _normalize_humidity_pct(value: Any) -> Optional[float]:
    numeric = _to_optional_float(value)
    if numeric is None:
        return None
    return numeric


def _parse_observed_at(value: Any) -> datetime:
    """Parse EcoWitt timestamps.

    We accept a few common shapes (ISO-8601, "YYYY-MM-DD HH:MM:SS", or Unix seconds/ms).
    If parsing fails, we treat it as missing and let callers fall back to capture time.
    """

    if value is None:
        raise ValueError("Missing observation timestamp")

    if isinstance(value, (int, float)):
        numeric = float(value)
        if numeric > 10**12:
            numeric /= 1000.0
        return datetime.fromtimestamp(numeric, tz=timezone.utc)

    raw = str(value).strip()
    if not raw:
        raise ValueError("Missing observation timestamp")

    # Normalize "Z" suffix for fromisoformat.
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(raw)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except ValueError:
        pass

    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y/%m/%d %H:%M:%S"):
        try:
            parsed = datetime.strptime(raw, fmt)  # noqa: DTZ007 - explicitly forced to UTC below
            return parsed.replace(tzinfo=timezone.utc)
        except ValueError:
            continue

    raise ValueError(f"Unrecognized observation timestamp: {value!r}")


def _read_sensor(data: Mapping[str, Any], *path: str) -> tuple[Any, Any]:
    node: Any = data
    for key in path:
        if not isinstance(node, Mapping):
            return None, None
        node = node.get(key)

    if isinstance(node, Mapping):
        return node.get("value"), node.get("unit")
    return None, None


def map_ecowitt_realtime(
    payload: Mapping[str, Any],
    *,
    location: Location,
    station: str | None,
    provider: str = "ecowitt",
    capture_time_utc: datetime | None = None,
) -> Observation:
    """Map EcoWitt Cloud real-time payload to :class:`~wxbench.domain.models.Observation`."""

    data: Any = payload.get("data")
    if not isinstance(data, Mapping):
        raise ValueError("Payload missing data")

    observed_at_raw = payload.get("time")
    if observed_at_raw is None:
        observed_at_raw = data.get("time")

    if capture_time_utc is None:
        capture_time_utc = datetime.now(timezone.utc)

    try:
        observed_at = _parse_observed_at(observed_at_raw)
    except ValueError:
        observed_at = capture_time_utc

    temp_value, temp_unit = _read_sensor(data, "outdoor", "temperature")
    temperature_c = _normalize_temperature_c(temp_value, temp_unit)
    if temperature_c is None:
        raise ValueError("Missing outdoor temperature in payload")

    humidity_value, _humidity_unit = _read_sensor(data, "outdoor", "humidity")
    relative_humidity = _normalize_humidity_pct(humidity_value)

    wind_value, wind_unit = _read_sensor(data, "wind", "wind_speed")
    wind_speed_kph = _normalize_wind_kph(wind_value, wind_unit)

    gust_value, gust_unit = _read_sensor(data, "wind", "wind_gust")
    wind_gust_kph = _normalize_wind_kph(gust_value, gust_unit)

    wind_dir_value, _wind_dir_unit = _read_sensor(data, "wind", "wind_direction")
    wind_direction_deg = _to_optional_int(wind_dir_value)

    pressure_rel_value, pressure_rel_unit = _read_sensor(data, "pressure", "relative")
    pressure_kpa = _normalize_pressure_kpa(pressure_rel_value, pressure_rel_unit)

    pressure_abs_value, pressure_abs_unit = _read_sensor(data, "pressure", "absolute")
    pressure_absolute_kpa = _normalize_pressure_kpa(pressure_abs_value, pressure_abs_unit)

    hourly_value, hourly_unit = _read_sensor(data, "rainfall", "hourly")
    precipitation_last_hour_mm = _normalize_precip_mm(hourly_value, hourly_unit)

    daily_value, daily_unit = _read_sensor(data, "rainfall", "daily")
    precipitation_daily_mm = _normalize_precip_mm(daily_value, daily_unit)

    weekly_value, weekly_unit = _read_sensor(data, "rainfall", "weekly")
    precipitation_weekly_mm = _normalize_precip_mm(weekly_value, weekly_unit)

    monthly_value, monthly_unit = _read_sensor(data, "rainfall", "monthly")
    precipitation_monthly_mm = _normalize_precip_mm(monthly_value, monthly_unit)

    yearly_value, yearly_unit = _read_sensor(data, "rainfall", "yearly")
    precipitation_yearly_mm = _normalize_precip_mm(yearly_value, yearly_unit)

    event_value, event_unit = _read_sensor(data, "rainfall", "event")
    precipitation_event_mm = _normalize_precip_mm(event_value, event_unit)

    uvi_value, _uvi_unit = _read_sensor(data, "solar_and_uvi", "uvi")
    uv_index = _to_optional_float(uvi_value)

    solar_value, solar_unit = _read_sensor(data, "solar_and_uvi", "solar")
    solar_radiation_wm2 = _to_optional_float(solar_value)

    return Observation(
        provider=provider,
        station=station,
        location=location,
        observed_at=observed_at,
        temperature_c=temperature_c,
        relative_humidity=relative_humidity,
        wind_speed_kph=wind_speed_kph,
        wind_gust_kph=wind_gust_kph,
        wind_direction_deg=wind_direction_deg,
        pressure_kpa=pressure_kpa,
        pressure_absolute_kpa=pressure_absolute_kpa,
        precipitation_last_hour_mm=precipitation_last_hour_mm,
        precipitation_daily_mm=precipitation_daily_mm,
        precipitation_weekly_mm=precipitation_weekly_mm,
        precipitation_monthly_mm=precipitation_monthly_mm,
        precipitation_yearly_mm=precipitation_yearly_mm,
        precipitation_event_mm=precipitation_event_mm,
        uv_index=uv_index,
        solar_radiation_wm2=solar_radiation_wm2,
    )
