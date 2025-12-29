"""Mapping helpers for AmbientWeather payloads."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping, MutableMapping, Optional, Sequence

from wxbench.domain.models import Location, Observation


INHG_TO_KPA = 3.386389
MPH_TO_KPH = 1.60934
INCH_TO_MM = 25.4


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


def _f_to_c(value: Optional[float]) -> Optional[float]:
    if value is None:
        return None
    return (value - 32.0) * 5.0 / 9.0


def _mph_to_kph(value: Optional[float]) -> Optional[float]:
    if value is None:
        return None
    return value * MPH_TO_KPH


def _inHg_to_kpa(value: Optional[float]) -> Optional[float]:
    if value is None:
        return None
    return value * INHG_TO_KPA


def _inches_to_mm(value: Optional[float]) -> Optional[float]:
    if value is None:
        return None
    return value * INCH_TO_MM


def _parse_observed_at(timestamp: Any) -> datetime:
    if timestamp is None:
        raise ValueError("Missing observation timestamp")

    numeric = float(timestamp)
    # Ambient Weather emits milliseconds since epoch; fall back to seconds if already small.
    if numeric > 10**12:
        numeric /= 1000.0

    return datetime.fromtimestamp(numeric, tz=timezone.utc)


def _extract_coords(info: Mapping[str, Any]) -> tuple[float, float]:
    coords: Any = info.get("coords")
    if isinstance(coords, Mapping):
        nested = coords.get("coords")
        if isinstance(nested, Mapping):
            lat = nested.get("lat") or nested.get("latitude")
            lon = nested.get("lon") or nested.get("longitude")
        else:
            lat = coords.get("lat") or coords.get("latitude")
            lon = coords.get("lon") or coords.get("longitude")
    elif isinstance(coords, Sequence) and not isinstance(coords, (str, bytes)):
        if len(coords) < 2:
            lat = lon = None
        else:
            lat, lon = coords[0], coords[1]
    else:
        lat = lon = None

    if lat is None or lon is None:
        raise ValueError("Missing coordinates for device")

    return float(lat), float(lon)


def _select_device(devices: Sequence[Mapping[str, Any]], preferred_mac: Optional[str]) -> Mapping[str, Any]:
    if not devices:
        raise ValueError("No devices found in payload")

    # Selection rule: prefer an explicit MAC (env override or parameter), otherwise choose
    # the first device after sorting by MAC address for determinism.
    if preferred_mac:
        for device in devices:
            mac = str(device.get("macAddress") or "")
            if mac.lower() == preferred_mac.lower():
                return device
        raise ValueError(f"Device with MAC {preferred_mac} not found")

    return sorted(devices, key=lambda dev: str(dev.get("macAddress") or ""))[0]


def map_ambient_weather_observation(
    payload: Sequence[Mapping[str, Any]], *, provider: str = "ambient_weather", device_mac: Optional[str] = None
) -> Observation:
    device = _select_device(payload, device_mac)

    last_data: MutableMapping[str, Any] = device.get("lastData") or {}
    if not last_data:
        raise ValueError("Device payload missing lastData")

    info: Mapping[str, Any] = device.get("info") or {}
    latitude, longitude = _extract_coords(info)

    observed_at = _parse_observed_at(last_data.get("dateutc"))

    temperature_f = _to_optional_float(last_data.get("tempf"))
    if temperature_f is None:
        temperature_f = _to_optional_float(last_data.get("tempOut"))
    if temperature_f is None:
        temperature_c_metric = _to_optional_float(last_data.get("tempc"))
    else:
        temperature_c_metric = None

    temperature_in_f = _to_optional_float(last_data.get("tempinf"))
    if temperature_in_f is None:
        temperature_in_f = _to_optional_float(last_data.get("tempIn"))

    feels_like_f = _to_optional_float(last_data.get("feelsLike"))
    feels_like_in_f = _to_optional_float(last_data.get("feelsLikein"))

    dewpoint_f = _to_optional_float(last_data.get("dewPoint"))
    if dewpoint_f is None:
        dewpoint_f = _to_optional_float(last_data.get("dewptf"))
    if dewpoint_f is None:
        dewpoint_c_metric = _to_optional_float(last_data.get("dewpt"))
    else:
        dewpoint_c_metric = None

    dewpoint_in_f = _to_optional_float(last_data.get("dewPointin"))
    if dewpoint_in_f is None:
        dewpoint_in_f = _to_optional_float(last_data.get("dewptin"))

    wind_speed_mph = _to_optional_float(last_data.get("windspeedmph"))
    if wind_speed_mph is None:
        wind_speed_mph = _to_optional_float(last_data.get("windSpeed"))

    wind_gust_mph = _to_optional_float(last_data.get("windgustmph"))
    max_daily_gust_mph = _to_optional_float(last_data.get("maxdailygust"))

    pressure_inhg = _to_optional_float(last_data.get("baromrelin"))
    if pressure_inhg is None:
        pressure_inhg = _to_optional_float(last_data.get("baromabsin"))
    if pressure_inhg is None:
        pressure_inhg = _to_optional_float(last_data.get("barometer"))

    pressure_abs_inhg = _to_optional_float(last_data.get("baromabsin"))

    precipitation_in = _to_optional_float(last_data.get("hourlyrainin"))
    if precipitation_in is None:
        precipitation_in = _to_optional_float(last_data.get("hourlyrain"))

    precipitation_daily_in = _to_optional_float(last_data.get("dailyrainin"))
    precipitation_weekly_in = _to_optional_float(last_data.get("weeklyrainin"))
    precipitation_monthly_in = _to_optional_float(last_data.get("monthlyrainin"))
    precipitation_yearly_in = _to_optional_float(last_data.get("yearlyrainin"))
    precipitation_event_in = _to_optional_float(last_data.get("eventrainin"))
    battery_in = _to_optional_float(last_data.get("battin"))
    battery_out = _to_optional_float(last_data.get("battout"))

    return Observation(
        provider=provider,
        station=info.get("name") or device.get("macAddress"),
        location=Location(latitude=latitude, longitude=longitude),
        observed_at=observed_at,
        temperature_c=temperature_c_metric if temperature_c_metric is not None else _f_to_c(temperature_f),
        temperature_apparent_c=_f_to_c(feels_like_f),
        temperature_in_c=_f_to_c(temperature_in_f),
        temperature_apparent_in_c=_f_to_c(feels_like_in_f),
        dewpoint_c=dewpoint_c_metric if dewpoint_c_metric is not None else _f_to_c(dewpoint_f),
        dewpoint_in_c=_f_to_c(dewpoint_in_f),
        wind_speed_kph=_mph_to_kph(wind_speed_mph),
        wind_gust_kph=_mph_to_kph(wind_gust_mph),
        wind_gust_daily_max_kph=_mph_to_kph(max_daily_gust_mph),
        wind_direction_deg=_to_optional_int(last_data.get("winddir")),
        wind_direction_avg_10m_deg=_to_optional_int(last_data.get("winddir_avg10m")),
        pressure_kpa=_inHg_to_kpa(pressure_inhg),
        pressure_absolute_kpa=_inHg_to_kpa(pressure_abs_inhg),
        relative_humidity=_to_optional_float(last_data.get("humidity")),
        relative_humidity_in=_to_optional_float(last_data.get("humidityin")),
        visibility_km=None,
        condition=None,
        precipitation_last_hour_mm=_inches_to_mm(precipitation_in),
        precipitation_daily_mm=_inches_to_mm(precipitation_daily_in),
        precipitation_weekly_mm=_inches_to_mm(precipitation_weekly_in),
        precipitation_monthly_mm=_inches_to_mm(precipitation_monthly_in),
        precipitation_yearly_mm=_inches_to_mm(precipitation_yearly_in),
        precipitation_event_mm=_inches_to_mm(precipitation_event_in),
        uv_index=_to_optional_float(last_data.get("uv")),
        solar_radiation_wm2=_to_optional_float(last_data.get("solarradiation")),
        battery_in=battery_in,
        battery_out=battery_out,
    )


__all__ = ["map_ambient_weather_observation"]
