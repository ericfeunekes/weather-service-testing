from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import yaml


def _merge_dicts(base: Mapping[str, Any], override: Mapping[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, Mapping) and isinstance(base.get(key), Mapping):
            merged[key] = _merge_dicts(base.get(key, {}), value)
        else:
            merged[key] = value
    return merged


@dataclass(frozen=True)
class SamplingConfig:
    distance_km: float
    time_cap_minutes: float


@dataclass(frozen=True)
class OutputConfig:
    format: str
    pdf: bool
    output_path: str | None = None
    pdf_path: str | None = None


@dataclass(frozen=True)
class RouteConfig:
    origin: str
    destination: str
    timezone: str
    travel_mode: str
    routing_preference: str
    units: str
    region_code: str | None = None


@dataclass(frozen=True)
class MscConfig:
    mode: str


@dataclass(frozen=True)
class TripBriefConfig:
    route: RouteConfig
    sampling: SamplingConfig
    output: OutputConfig
    msc: MscConfig
    name: str | None = None


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    raw = yaml.safe_load(path.read_text())
    return raw if isinstance(raw, dict) else {}


def load_trip_brief_config(
    *,
    config_path: Path,
    route_id: str | None,
    origin: str | None,
    destination: str | None,
    sampling_distance_km: float | None,
    sampling_time_cap_minutes: float | None,
    output_format: str | None,
    output_path: str | None,
    pdf: bool | None,
    pdf_path: str | None,
    timezone: str | None,
) -> TripBriefConfig:
    data = _load_yaml(config_path)
    defaults = data.get("defaults", {}) if isinstance(data.get("defaults"), Mapping) else {}
    routes = data.get("routes", {}) if isinstance(data.get("routes"), Mapping) else {}

    route_block: dict[str, Any] = {}
    if route_id:
        route_value = routes.get(route_id)
        if not isinstance(route_value, Mapping):
            raise ValueError(f"Unknown route preset: {route_id}")
        route_block = dict(route_value)

    if origin:
        route_block["origin"] = origin
    if destination:
        route_block["destination"] = destination
    if timezone:
        route_block["timezone"] = timezone

    merged = _merge_dicts(defaults, route_block)

    route_defaults = defaults.get("route", {}) if isinstance(defaults.get("route"), Mapping) else {}
    route_overrides = route_block.get("route", {}) if isinstance(route_block.get("route"), Mapping) else {}
    route_cfg = _merge_dicts(route_defaults, route_overrides)

    sampling_defaults = defaults.get("sampling", {}) if isinstance(defaults.get("sampling"), Mapping) else {}
    sampling_overrides = route_block.get("sampling", {}) if isinstance(route_block.get("sampling"), Mapping) else {}
    sampling_cfg = _merge_dicts(sampling_defaults, sampling_overrides)
    if sampling_distance_km is not None:
        sampling_cfg["distance_km"] = sampling_distance_km
    if sampling_time_cap_minutes is not None:
        sampling_cfg["time_cap_minutes"] = sampling_time_cap_minutes

    output_defaults = defaults.get("output", {}) if isinstance(defaults.get("output"), Mapping) else {}
    output_overrides = route_block.get("output", {}) if isinstance(route_block.get("output"), Mapping) else {}
    output_cfg = _merge_dicts(output_defaults, output_overrides)
    if output_format:
        output_cfg["format"] = output_format
    if output_path:
        output_cfg["output_path"] = output_path
    if pdf is not None:
        output_cfg["pdf"] = pdf
    if pdf_path:
        output_cfg["pdf_path"] = pdf_path

    msc_defaults = defaults.get("msc", {}) if isinstance(defaults.get("msc"), Mapping) else {}
    msc_overrides = route_block.get("msc", {}) if isinstance(route_block.get("msc"), Mapping) else {}
    msc_cfg = _merge_dicts(msc_defaults, msc_overrides)

    origin_value = merged.get("origin")
    destination_value = merged.get("destination")
    if not origin_value or not destination_value:
        raise ValueError("Route origin and destination are required")

    return TripBriefConfig(
        name=merged.get("name"),
        route=RouteConfig(
            origin=str(origin_value),
            destination=str(destination_value),
            timezone=str(merged.get("timezone") or "America/Halifax"),
            travel_mode=str(route_cfg.get("travel_mode") or "DRIVE"),
            routing_preference=str(route_cfg.get("routing_preference") or "TRAFFIC_AWARE"),
            units=str(route_cfg.get("units") or "METRIC"),
            region_code=str(route_cfg.get("region_code")) if route_cfg.get("region_code") else None,
        ),
        sampling=SamplingConfig(
            distance_km=float(sampling_cfg.get("distance_km") or 50.0),
            time_cap_minutes=float(sampling_cfg.get("time_cap_minutes") or 40.0),
        ),
        output=OutputConfig(
            format=str(output_cfg.get("format") or "markdown"),
            pdf=bool(output_cfg.get("pdf") or False),
            output_path=str(output_cfg.get("output_path")) if output_cfg.get("output_path") else None,
            pdf_path=str(output_cfg.get("pdf_path")) if output_cfg.get("pdf_path") else None,
        ),
        msc=MscConfig(mode=str(msc_cfg.get("mode") or "endpoints")),
    )
