from __future__ import annotations

import argparse
import os
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx

from wxbench.domain.models import Observation
from wxbench.providers.google_routes import fetch_google_route
from wxbench.providers.msc_geomet import fetch_msc_geomet_observation
from wxbench.providers.weatherkit import fetch_weatherkit_bundle
from wxbench.trip_brief.config import load_trip_brief_config
from wxbench.trip_brief.pdf import render_pdf
from wxbench.trip_brief.runner import generate_trip_brief


def _require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value.strip()


def _parse_depart_time(value: str, timezone: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=ZoneInfo(timezone))
    return parsed


def run_trip_brief(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate a trip brief from Google Routes + WeatherKit.")
    parser.add_argument("--config", default="configs/routes.yaml")
    parser.add_argument("--route", help="Route preset ID from configs/routes.yaml")
    parser.add_argument("--origin")
    parser.add_argument("--destination")
    parser.add_argument("--depart", required=True, help="Departure time in ISO format")
    parser.add_argument("--distance-km", type=float)
    parser.add_argument("--time-cap-min", type=float)
    parser.add_argument("--timezone")
    parser.add_argument("--format", choices=["markdown"], default=None)
    parser.add_argument("--output", help="Write markdown output to file")
    parser.add_argument("--pdf", action="store_true", help="Write PDF report")
    parser.add_argument("--pdf-path", help="PDF output path")
    parser.add_argument("--msc-mode", choices=["none", "endpoints", "corridor"], default=None)

    args = parser.parse_args(argv)

    config = load_trip_brief_config(
        config_path=Path(args.config),
        route_id=args.route,
        origin=args.origin,
        destination=args.destination,
        sampling_distance_km=args.distance_km,
        sampling_time_cap_minutes=args.time_cap_min,
        output_format=args.format,
        output_path=args.output,
        pdf=args.pdf if args.pdf else None,
        pdf_path=args.pdf_path,
        timezone=args.timezone,
    )

    if args.msc_mode:
        config = config.__class__(
            route=config.route,
            sampling=config.sampling,
            output=config.output,
            msc=config.msc.__class__(mode=args.msc_mode),
            name=config.name,
        )

    depart_time = _parse_depart_time(args.depart, config.route.timezone)

    maps_key = _require_env("WX_GOOGLE_MAPS_API_KEY")
    team_id = _require_env("WX_WEATHERKIT_TEAM_ID")
    service_id = _require_env("WX_WEATHERKIT_SERVICE_ID")
    key_id = _require_env("WX_WEATHERKIT_KEY_ID")
    key_path = _require_env("WX_WEATHERKIT_KEY_PATH")
    country_code = os.getenv("WX_WEATHERKIT_COUNTRY_CODE", "CA").strip() or "CA"

    with httpx.Client() as client:
        def route_fetcher():
            return fetch_google_route(
                origin=config.route.origin,
                destination=config.route.destination,
                api_key=maps_key,
                client=client,
                travel_mode=config.route.travel_mode,
                routing_preference=config.route.routing_preference,
                units=config.route.units,
                region_code=config.route.region_code,
            )

        def weather_fetcher(lat: float, lon: float, tz_name: str):
            bundle = fetch_weatherkit_bundle(
                latitude=lat,
                longitude=lon,
                timezone_name=tz_name,
                client=client,
                team_id=team_id,
                service_id=service_id,
                key_id=key_id,
                key_path=key_path,
                country_code=country_code,
            )
            return bundle.hourly

        def msc_fetcher(lat: float, lon: float) -> Observation:
            return fetch_msc_geomet_observation(latitude=lat, longitude=lon, client=client)

        name = config.name or f"{config.route.origin} → {config.route.destination}"
        result = generate_trip_brief(
            name=name,
            depart_time=depart_time,
            timezone=config.route.timezone,
            sampling_distance_km=config.sampling.distance_km,
            sampling_time_cap_minutes=config.sampling.time_cap_minutes,
            route_fetcher=route_fetcher,
            weather_fetcher=weather_fetcher,
            msc_mode=config.msc.mode,
            msc_fetcher=msc_fetcher,
        )

    if config.output.output_path:
        output_path = Path(config.output.output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(result.markdown)
    else:
        print(result.markdown)

    if config.output.pdf or (config.output.pdf_path or args.pdf_path):
        pdf_path = config.output.pdf_path or args.pdf_path or "reports/trip_brief.pdf"
        Path(pdf_path).parent.mkdir(parents=True, exist_ok=True)
        render_pdf(pdf_path, title="Trip Brief", subtitle=result.subtitle, rows=result.rows, summary=result.summary)
        print(f"PDF written to: {pdf_path}")

    return 0


def main() -> None:
    raise SystemExit(run_trip_brief())
