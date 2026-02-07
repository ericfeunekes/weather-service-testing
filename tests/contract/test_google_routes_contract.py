from __future__ import annotations

import os
from pathlib import Path

import httpx
import pytest
import vcr


CASSETTE_DIR = Path(__file__).parent / "cassettes"

recorder = vcr.VCR(
    cassette_library_dir=str(CASSETTE_DIR),
    record_mode=os.getenv("WX_VCR_RECORD_MODE", "none"),
    filter_headers=["x-goog-api-key"],
    match_on=["method", "scheme", "host", "port", "path", "query", "body"],
)

RECORDING = recorder.record_mode != "none"


def _require_env(var: str, *, provider: str) -> str:
    value = os.getenv(var)
    if value:
        value = value.strip()
    if RECORDING and not value:
        pytest.skip(f"Set {var} to hit the live {provider} API")
    return value or ""


def _google_maps_key() -> str:
    return _require_env("WX_GOOGLE_MAPS_API_KEY", provider="Google Routes") or "demo-key"


def _compute_route(client: httpx.Client, api_key: str) -> dict:
    url = "https://routes.googleapis.com/directions/v2:computeRoutes"
    headers = {
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": "routes.duration,routes.distanceMeters,routes.polyline.encodedPolyline",
        "Content-Type": "application/json",
    }
    payload = {
        "origin": {"location": {"latLng": {"latitude": 47.6189, "longitude": -65.6517}}},
        "destination": {"location": {"latLng": {"latitude": 44.6488, "longitude": -63.5752}}},
        "travelMode": "DRIVE",
        "routingPreference": "TRAFFIC_AWARE",
        "units": "METRIC",
        "polylineQuality": "OVERVIEW",
        "polylineEncoding": "ENCODED_POLYLINE",
    }
    response = client.post(url, headers=headers, json=payload, timeout=30.0)
    response.raise_for_status()
    return response.json()


def test_google_routes_contract() -> None:
    api_key = _google_maps_key()
    cassette_name = "google_routes_compute.yaml"

    with httpx.Client() as client, recorder.use_cassette(cassette_name):
        payload = _compute_route(client, api_key)

    routes = payload.get("routes") or []
    assert routes, "Expected at least one route"
    route = routes[0]
    assert isinstance(route.get("duration"), str)
    assert isinstance(route.get("distanceMeters"), int)
    polyline = (route.get("polyline") or {}).get("encodedPolyline")
    assert isinstance(polyline, str)
