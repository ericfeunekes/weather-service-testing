"""Aggregation helpers for forecasts."""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, time, timedelta, timezone
from statistics import mean
from typing import Iterable
from zoneinfo import ZoneInfo

from wxbench.domain.models import ForecastPeriod


def aggregate_daily_from_periods(
    periods: Iterable[ForecastPeriod], *, tz_name: str, quality_flag: str = "derived_daily_from_periods"
) -> list[ForecastPeriod]:
    """Aggregate forecast periods into daily summaries by local day."""

    grouped: dict[str, list[ForecastPeriod]] = defaultdict(list)
    for period in periods:
        day = period.start_time.astimezone(ZoneInfo(tz_name)).date().isoformat()
        grouped[day].append(period)

    daily_periods: list[ForecastPeriod] = []
    for day, entries in sorted(grouped.items()):
        if not entries:
            continue
        provider = entries[0].provider
        location = entries[0].location
        issued_at = entries[0].issued_at

        temps = [p.temperature_c for p in entries if p.temperature_c is not None]
        temp_apparent = [p.temperature_apparent_c for p in entries if p.temperature_apparent_c is not None]
        temp_apparent_shade = [
            p.temperature_apparent_shade_c for p in entries if p.temperature_apparent_shade_c is not None
        ]
        temp_apparent_alt = [
            p.temperature_apparent_alt_c for p in entries if p.temperature_apparent_alt_c is not None
        ]
        temp_wind_chill = [p.temperature_wind_chill_c for p in entries if p.temperature_wind_chill_c is not None]
        temp_wet_bulb = [p.temperature_wet_bulb_c for p in entries if p.temperature_wet_bulb_c is not None]
        temp_wet_bulb_globe = [
            p.temperature_wet_bulb_globe_c for p in entries if p.temperature_wet_bulb_globe_c is not None
        ]
        dewpoints = [p.dewpoint_c for p in entries if p.dewpoint_c is not None]
        temp_highs = [p.temperature_high_c for p in entries if p.temperature_high_c is not None]
        temp_lows = [p.temperature_low_c for p in entries if p.temperature_low_c is not None]
        humidity = [p.relative_humidity for p in entries if p.relative_humidity is not None]
        visibility = [p.visibility_km for p in entries if p.visibility_km is not None]
        pressure_sea = [p.pressure_sea_level_kpa for p in entries if p.pressure_sea_level_kpa is not None]
        pressure_surface = [
            p.pressure_surface_kpa for p in entries if p.pressure_surface_kpa is not None
        ]
        altimeter = [p.altimeter_kpa for p in entries if p.altimeter_kpa is not None]
        cloud_cover = [p.cloud_cover_pct for p in entries if p.cloud_cover_pct is not None]
        cloud_base = [p.cloud_base_km for p in entries if p.cloud_base_km is not None]
        cloud_ceiling = [p.cloud_ceiling_km for p in entries if p.cloud_ceiling_km is not None]
        uv_index = [p.uv_index for p in entries if p.uv_index is not None]
        uv_health = [p.uv_health_concern for p in entries if p.uv_health_concern is not None]
        precip_probs = [p.precipitation_probability for p in entries if p.precipitation_probability is not None]
        precip_prob_rain = [
            p.precipitation_probability_rain for p in entries if p.precipitation_probability_rain is not None
        ]
        precip_prob_snow = [
            p.precipitation_probability_snow for p in entries if p.precipitation_probability_snow is not None
        ]
        precip_prob_ice = [
            p.precipitation_probability_ice for p in entries if p.precipitation_probability_ice is not None
        ]
        precip_prob_thunder = [
            p.precipitation_probability_thunderstorm
            for p in entries
            if p.precipitation_probability_thunderstorm is not None
        ]
        precip_amounts = [p.precipitation_mm for p in entries if p.precipitation_mm is not None]
        precip_rain = [p.precipitation_amount_rain_mm for p in entries if p.precipitation_amount_rain_mm is not None]
        precip_snow = [p.precipitation_amount_snow_mm for p in entries if p.precipitation_amount_snow_mm is not None]
        precip_sleet = [
            p.precipitation_amount_sleet_mm for p in entries if p.precipitation_amount_sleet_mm is not None
        ]
        precip_ice = [p.precipitation_amount_ice_mm for p in entries if p.precipitation_amount_ice_mm is not None]
        precip_snow_lwe = [
            p.precipitation_amount_snow_lwe_mm for p in entries if p.precipitation_amount_snow_lwe_mm is not None
        ]
        precip_sleet_lwe = [
            p.precipitation_amount_sleet_lwe_mm
            for p in entries
            if p.precipitation_amount_sleet_lwe_mm is not None
        ]
        precip_ice_lwe = [
            p.precipitation_amount_ice_lwe_mm for p in entries if p.precipitation_amount_ice_lwe_mm is not None
        ]
        precip_rate_rain = [
            p.precipitation_rate_rain_mm_hr for p in entries if p.precipitation_rate_rain_mm_hr is not None
        ]
        precip_rate_snow = [
            p.precipitation_rate_snow_mm_hr for p in entries if p.precipitation_rate_snow_mm_hr is not None
        ]
        precip_rate_sleet = [
            p.precipitation_rate_sleet_mm_hr for p in entries if p.precipitation_rate_sleet_mm_hr is not None
        ]
        precip_rate_freezing = [
            p.precipitation_rate_freezing_rain_mm_hr
            for p in entries
            if p.precipitation_rate_freezing_rain_mm_hr is not None
        ]
        precip_rate_ice = [
            p.precipitation_rate_ice_mm_hr for p in entries if p.precipitation_rate_ice_mm_hr is not None
        ]
        snow_depth = [p.snow_depth_cm for p in entries if p.snow_depth_cm is not None]
        evapotranspiration = [p.evapotranspiration_mm for p in entries if p.evapotranspiration_mm is not None]
        solar_irradiance = [p.solar_irradiance_wm2 for p in entries if p.solar_irradiance_wm2 is not None]
        sun_hours = [p.sun_hours for p in entries if p.sun_hours is not None]
        wind_speeds = [p.wind_speed_kph for p in entries if p.wind_speed_kph is not None]
        wind_gusts = [p.wind_gust_kph for p in entries if p.wind_gust_kph is not None]
        wind_dirs = [p.wind_direction_deg for p in entries if p.wind_direction_deg is not None]

        day_date = entries[0].start_time.astimezone(ZoneInfo(tz_name)).date()
        local_start = datetime.combine(day_date, time.min, tzinfo=ZoneInfo(tz_name))
        start_time = local_start.astimezone(timezone.utc)
        end_time = start_time + timedelta(days=1)

        daily_periods.append(
            ForecastPeriod(
                provider=provider,
                location=location,
                issued_at=issued_at,
                start_time=start_time,
                end_time=end_time,
                temperature_c=mean(temps) if temps else None,
                temperature_apparent_c=mean(temp_apparent) if temp_apparent else None,
                temperature_apparent_shade_c=mean(temp_apparent_shade) if temp_apparent_shade else None,
                temperature_apparent_alt_c=mean(temp_apparent_alt) if temp_apparent_alt else None,
                temperature_wind_chill_c=mean(temp_wind_chill) if temp_wind_chill else None,
                temperature_wet_bulb_c=mean(temp_wet_bulb) if temp_wet_bulb else None,
                temperature_wet_bulb_globe_c=mean(temp_wet_bulb_globe) if temp_wet_bulb_globe else None,
                dewpoint_c=mean(dewpoints) if dewpoints else None,
                temperature_high_c=max(temp_highs) if temp_highs else (max(temps) if temps else None),
                temperature_low_c=min(temp_lows) if temp_lows else (min(temps) if temps else None),
                precipitation_probability=max(precip_probs) if precip_probs else None,
                precipitation_probability_rain=max(precip_prob_rain) if precip_prob_rain else None,
                precipitation_probability_snow=max(precip_prob_snow) if precip_prob_snow else None,
                precipitation_probability_ice=max(precip_prob_ice) if precip_prob_ice else None,
                precipitation_probability_thunderstorm=max(precip_prob_thunder) if precip_prob_thunder else None,
                precipitation_mm=sum(precip_amounts) if precip_amounts else None,
                precipitation_amount_rain_mm=sum(precip_rain) if precip_rain else None,
                precipitation_amount_snow_mm=sum(precip_snow) if precip_snow else None,
                precipitation_amount_sleet_mm=sum(precip_sleet) if precip_sleet else None,
                precipitation_amount_ice_mm=sum(precip_ice) if precip_ice else None,
                precipitation_amount_snow_lwe_mm=sum(precip_snow_lwe) if precip_snow_lwe else None,
                precipitation_amount_sleet_lwe_mm=sum(precip_sleet_lwe) if precip_sleet_lwe else None,
                precipitation_amount_ice_lwe_mm=sum(precip_ice_lwe) if precip_ice_lwe else None,
                precipitation_rate_rain_mm_hr=mean(precip_rate_rain) if precip_rate_rain else None,
                precipitation_rate_snow_mm_hr=mean(precip_rate_snow) if precip_rate_snow else None,
                precipitation_rate_sleet_mm_hr=mean(precip_rate_sleet) if precip_rate_sleet else None,
                precipitation_rate_freezing_rain_mm_hr=mean(precip_rate_freezing) if precip_rate_freezing else None,
                precipitation_rate_ice_mm_hr=mean(precip_rate_ice) if precip_rate_ice else None,
                summary=None,
                wind_speed_kph=max(wind_speeds) if wind_speeds else None,
                wind_gust_kph=max(wind_gusts) if wind_gusts else None,
                wind_direction_deg=wind_dirs[0] if wind_dirs else None,
                uv_index=max(uv_index) if uv_index else None,
                uv_health_concern=max(uv_health) if uv_health else None,
                relative_humidity=mean(humidity) if humidity else None,
                visibility_km=mean(visibility) if visibility else None,
                pressure_sea_level_kpa=mean(pressure_sea) if pressure_sea else None,
                pressure_surface_kpa=mean(pressure_surface) if pressure_surface else None,
                altimeter_kpa=mean(altimeter) if altimeter else None,
                cloud_cover_pct=mean(cloud_cover) if cloud_cover else None,
                cloud_base_km=mean(cloud_base) if cloud_base else None,
                cloud_ceiling_km=mean(cloud_ceiling) if cloud_ceiling else None,
                snow_depth_cm=max(snow_depth) if snow_depth else None,
                evapotranspiration_mm=sum(evapotranspiration) if evapotranspiration else None,
                solar_irradiance_wm2=mean(solar_irradiance) if solar_irradiance else None,
                sun_hours=sum(sun_hours) if sun_hours else None,
            )
        )

    return daily_periods


__all__ = ["aggregate_daily_from_periods"]
