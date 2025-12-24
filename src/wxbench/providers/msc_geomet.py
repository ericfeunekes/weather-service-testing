"""Adapter for Environment Canada MSC GeoMet API."""
from __future__ import annotations

from typing import Optional

import httpx

from wxbench.domain.mappers.msc_geomet import map_msc_geomet_forecast, map_msc_geomet_observation
from wxbench.providers._http import DEFAULT_TIMEOUT, send_with_retries

__all__ = ["fetch_msc_geomet_forecast", "fetch_msc_geomet_observation"]


BASE_URL = "https://api.weather.gc.ca"


def _build_common_params(latitude: float, longitude: float) -> dict[str, str]:
    return {"lat": str(latitude), "lon": str(longitude), "f": "json"}


def fetch_msc_geomet_observation(
    *,
    latitude: float,
    longitude: float,
    client: httpx.Client,
    base_url: str = BASE_URL,
    retries: int = 2,
    timeout: Optional[httpx.Timeout] | float | None = DEFAULT_TIMEOUT,
):
    """Fetch the latest observation feature for a coordinate pair."""

    request = client.build_request(
        "GET",
        f"{base_url}/collections/observations/point",
        params=_build_common_params(latitude, longitude),
        headers={"accept": "application/json"},
        timeout=timeout,
    )
    response = send_with_retries(client, request, retries=retries)
    return map_msc_geomet_observation(response.json())


def fetch_msc_geomet_forecast(
    *,
    latitude: float,
    longitude: float,
    client: httpx.Client,
    base_url: str = BASE_URL,
    retries: int = 2,
    timeout: Optional[httpx.Timeout] | float | None = DEFAULT_TIMEOUT,
):
    """Fetch forecast feature data for a coordinate pair."""

    request = client.build_request(
        "GET",
        f"{base_url}/collections/forecasts/point",
        params=_build_common_params(latitude, longitude),
        headers={"accept": "application/json"},
        timeout=timeout,
    )
    response = send_with_retries(client, request, retries=retries)
    return map_msc_geomet_forecast(response.json())
