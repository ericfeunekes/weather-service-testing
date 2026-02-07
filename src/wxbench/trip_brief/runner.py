from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Callable, Iterable
from zoneinfo import ZoneInfo

from wxbench.domain.models import ForecastPeriod, Observation
from wxbench.providers.google_routes import GoogleRoute
from wxbench.trip_brief.render import BriefRow, build_summary, classify_precip, render_markdown, select_hourly_period
from wxbench.trip_brief.sampling import decode_polyline, sample_route_points


@dataclass(frozen=True)
class TripBriefResult:
    markdown: str
    rows: list[BriefRow]
    summary: str
    msc_observations: list[Observation]
    subtitle: str


RouteFetcher = Callable[[], GoogleRoute]
WeatherFetcher = Callable[[float, float, str], Iterable[ForecastPeriod]]
MscFetcher = Callable[[float, float], Observation]


def generate_trip_brief(
    *,
    name: str,
    depart_time: datetime,
    timezone: str,
    sampling_distance_km: float,
    sampling_time_cap_minutes: float,
    route_fetcher: RouteFetcher,
    weather_fetcher: WeatherFetcher,
    msc_mode: str,
    msc_fetcher: MscFetcher | None = None,
) -> TripBriefResult:
    route = route_fetcher()
    geometry = decode_polyline(route.encoded_polyline)
    if not geometry:
        raise RuntimeError("Route polyline is empty")

    samples = sample_route_points(
        geometry,
        total_distance_km=route.distance_km,
        duration_seconds=route.duration_seconds,
        distance_km=sampling_distance_km,
        time_cap_minutes=sampling_time_cap_minutes,
        depart_time=depart_time,
    )

    rows: list[BriefRow] = []
    for sample in samples:
        hourly = list(weather_fetcher(sample.latitude, sample.longitude, timezone))
        period = select_hourly_period(hourly, sample.sample_time)
        if period is None:
            raise RuntimeError("No hourly forecast periods returned by weather provider")

        rows.append(
            BriefRow(
                time_local=sample.sample_time.astimezone(ZoneInfo(timezone)).strftime("%Y-%m-%d %H:%M"),
                distance_km=sample.distance_km,
                precip_type=classify_precip(
                    period.precipitation_mm,
                    period.precipitation_rate_snow_mm_hr,
                    period.temperature_c,
                ),
                precip_probability=period.precipitation_probability,
                precip_amount=period.precipitation_mm,
                snow_rate=period.precipitation_rate_snow_mm_hr,
                temperature_c=period.temperature_c,
                wind_kph=period.wind_speed_kph,
                gust_kph=period.wind_gust_kph,
                visibility_km=period.visibility_km,
            )
        )

    msc_observations: list[Observation] = []
    if msc_mode != "none" and msc_fetcher is not None:
        if msc_mode == "corridor":
            targets = samples
        elif msc_mode == "endpoints":
            targets = [samples[0], samples[-1]] if samples else []
        else:
            raise ValueError(f"Unknown MSC mode: {msc_mode}")

        for sample in targets:
            msc_observations.append(msc_fetcher(sample.latitude, sample.longitude))

    summary = build_summary(rows)
    subtitle = (
        f"{name} | Departure {depart_time.strftime('%Y-%m-%d %H:%M %Z')} | "
        f"Sampling {sampling_distance_km:.0f} km or {sampling_time_cap_minutes:.0f} min"
    )
    markdown = render_markdown(
        title="Trip Brief",
        subtitle=subtitle,
        rows=rows,
        summary=summary,
        msc_observations=msc_observations,
    )

    return TripBriefResult(
        markdown=markdown,
        rows=rows,
        summary=summary,
        msc_observations=msc_observations,
        subtitle=subtitle,
    )
