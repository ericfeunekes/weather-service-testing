"""Adapter for AmbientWeather observations."""
from __future__ import annotations

from typing import Optional

import httpx

from wxbench.domain.mappers.ambient_weather import map_ambient_weather_observation
from wxbench.providers._http import DEFAULT_TIMEOUT, send_with_retries
from wxbench.providers.errors import ProviderPayloadError

__all__ = ["fetch_ambient_weather_observation"]


BASE_URL = "https://api.ambientweather.net/v1"


def fetch_ambient_weather_observation(
    *,
    client: httpx.Client,
    api_key: Optional[str] = None,
    application_key: Optional[str] = None,
    base_url: str = BASE_URL,
    retries: int = 2,
    timeout: Optional[httpx.Timeout] | float | None = DEFAULT_TIMEOUT,
):
    """Fetch the latest observation from AmbientWeather."""

    request = client.build_request(
        "GET",
        f"{base_url}/devices",
        params={"applicationKey": application_key, "apiKey": api_key},
        headers={"accept": "application/json"},
        timeout=timeout,
    )
    response = send_with_retries(
        client,
        request,
        provider="ambient_weather",
        operation="observation",
        retries=retries,
    )

    try:
        payload = response.json()
    except (ValueError, httpx.HTTPError) as exc:
        raise ProviderPayloadError("ambient_weather", "observation", "Invalid JSON payload") from exc

    try:
        return map_ambient_weather_observation(payload)
    except ValueError as exc:
        raise ProviderPayloadError("ambient_weather", "observation", str(exc)) from exc
