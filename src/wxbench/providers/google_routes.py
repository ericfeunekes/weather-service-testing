"""Adapter for Google Routes API."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional

import httpx

from wxbench.providers._http import DEFAULT_TIMEOUT, send_with_retries
from wxbench.providers.errors import ProviderPayloadError


BASE_URL = "https://routes.googleapis.com"
DEFAULT_FIELD_MASK = "routes.duration,routes.distanceMeters,routes.polyline.encodedPolyline"


@dataclass(frozen=True)
class GoogleRoute:
    geometry: list[tuple[float, float]]
    distance_km: float
    duration_seconds: float
    encoded_polyline: str


def _parse_duration_seconds(raw: str) -> float:
    if not raw.endswith("s"):
        raise ValueError(f"Unexpected duration format: {raw}")
    return float(raw[:-1])


def fetch_google_route(
    *,
    origin: str,
    destination: str,
    api_key: str,
    client: httpx.Client,
    travel_mode: str = "DRIVE",
    routing_preference: str = "TRAFFIC_AWARE",
    units: str = "METRIC",
    region_code: Optional[str] = None,
    field_mask: str = DEFAULT_FIELD_MASK,
    base_url: str = BASE_URL,
    timeout: httpx.Timeout | float | None = DEFAULT_TIMEOUT,
    retries: int = 2,
) -> GoogleRoute:
    request = client.build_request(
        "POST",
        f"{base_url}/directions/v2:computeRoutes",
        headers={
            "X-Goog-Api-Key": api_key,
            "X-Goog-FieldMask": field_mask,
            "Content-Type": "application/json",
        },
        json={
            "origin": {"address": origin},
            "destination": {"address": destination},
            "travelMode": travel_mode,
            "routingPreference": routing_preference,
            "units": units,
            "polylineQuality": "OVERVIEW",
            "polylineEncoding": "ENCODED_POLYLINE",
            **({"regionCode": region_code} if region_code else {}),
        },
        timeout=timeout,
    )

    response = send_with_retries(
        client,
        request,
        provider="google_routes",
        operation="compute_routes",
        retries=retries,
    )

    try:
        payload = response.json()
    except (ValueError, httpx.HTTPError) as exc:
        raise ProviderPayloadError("google_routes", "compute_routes", "Invalid JSON payload") from exc

    routes: Iterable[dict] = payload.get("routes") or []
    if not routes:
        raise ProviderPayloadError("google_routes", "compute_routes", "Missing routes in payload")

    route = routes[0]
    duration_raw = route.get("duration")
    distance_meters = route.get("distanceMeters")
    polyline = (route.get("polyline") or {}).get("encodedPolyline")

    if not duration_raw or distance_meters is None or not polyline:
        raise ProviderPayloadError("google_routes", "compute_routes", "Missing required route fields")

    return GoogleRoute(
        geometry=[],
        distance_km=float(distance_meters) / 1000.0,
        duration_seconds=_parse_duration_seconds(str(duration_raw)),
        encoded_polyline=str(polyline),
    )
