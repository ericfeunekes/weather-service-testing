from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from wxbench.domain.models import ForecastPeriod, Observation


@dataclass(frozen=True)
class BriefRow:
    time_local: str
    distance_km: float
    precip_type: str
    precip_probability: float | None
    precip_amount: float | None
    snow_rate: float | None
    temperature_c: float | None
    wind_kph: float | None
    gust_kph: float | None
    visibility_km: float | None


def select_hourly_period(hourly: list[ForecastPeriod], sample_time: datetime) -> ForecastPeriod | None:
    if not hourly:
        return None
    for period in hourly:
        if period.start_time <= sample_time < period.end_time:
            return period
    return min(hourly, key=lambda period: abs(period.start_time - sample_time))


def classify_precip(precip_mm: float | None, snow_rate: float | None, temp_c: float | None) -> str:
    if snow_rate is not None and snow_rate >= 0.05:
        return "snow"
    if precip_mm is not None and precip_mm >= 0.05:
        if temp_c is None:
            return "mixed"
        return "rain" if temp_c > 0 else "mixed"
    return "none"


def fmt(value: float | None, digits: int = 1) -> str:
    if value is None:
        return "-"
    return f"{value:.{digits}f}"


def build_summary(rows: list[BriefRow]) -> str:
    precip_rows = [row for row in rows if row.precip_type != "none"]
    max_wind = max((row.wind_kph for row in rows if row.wind_kph is not None), default=None)
    max_gust = max((row.gust_kph for row in rows if row.gust_kph is not None), default=None)
    min_vis = min((row.visibility_km for row in rows if row.visibility_km is not None), default=None)

    lines: list[str] = []
    if precip_rows:
        max_prob = max((row.precip_probability or 0 for row in precip_rows), default=0)
        max_amount = max((row.precip_amount or 0 for row in precip_rows), default=0)
        lines.append(
            f"- Precip likely in {len(precip_rows)} sampled points; max chance {max_prob:.0f}% and max amount {max_amount:.1f} mm."
        )
    else:
        lines.append("- No precip indicated across sampled points.")

    if max_wind is not None:
        lines.append(f"- Peak sustained wind: {max_wind:.1f} kph.")
    if max_gust is not None:
        lines.append(f"- Peak gust: {max_gust:.1f} kph.")
    if min_vis is not None:
        lines.append(f"- Lowest visibility: {min_vis:.1f} km.")

    return "\n".join(lines)


def render_markdown(
    *,
    title: str,
    subtitle: str,
    rows: list[BriefRow],
    summary: str,
    msc_observations: list[Observation] | None = None,
) -> str:
    lines: list[str] = []
    lines.append(f"# {title}")
    lines.append("")
    lines.append(subtitle)
    lines.append("")
    lines.append(
        "| time_local | distance_km | precip_type | precip_probability | precip_amount_mm | snow_rate_mm_hr | temp_c | wind_kph | gust_kph | visibility_km |"
    )
    lines.append("|---|---:|---|---:|---:|---:|---:|---:|---:|---:|")
    for row in rows:
        lines.append(
            "| "
            + " | ".join(
                [
                    row.time_local,
                    f"{row.distance_km:.1f}",
                    row.precip_type,
                    fmt(row.precip_probability, 0),
                    fmt(row.precip_amount),
                    fmt(row.snow_rate),
                    fmt(row.temperature_c),
                    fmt(row.wind_kph),
                    fmt(row.gust_kph),
                    fmt(row.visibility_km),
                ]
            )
            + " |"
        )

    if msc_observations:
        lines.append("")
        lines.append("## MSC GeoMet observations")
        for obs in msc_observations:
            observed = obs.observed_at.isoformat()
            lines.append(
                f"- {observed} | {obs.location.latitude:.4f},{obs.location.longitude:.4f} | "
                f"temp {fmt(obs.temperature_c)}°C | wind {fmt(obs.wind_speed_kph)} kph | vis {fmt(obs.visibility_km)} km"
            )

    lines.append("")
    lines.append("## Summary")
    lines.append(summary)

    return "\n".join(lines)
