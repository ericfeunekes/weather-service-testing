"""Adapter for Tomorrow.io Weather API."""
from __future__ import annotations

from typing import Optional

import httpx

from wxbench.domain.mappers.tomorrow_io import map_tomorrow_io_forecast, map_tomorrow_io_observation
from wxbench.providers._http import DEFAULT_TIMEOUT, send_with_retries
from wxbench.providers.errors import ProviderPayloadError

__all__ = ["fetch_tomorrow_io_forecast", "fetch_tomorrow_io_observation"]


BASE_URL = "https://api.tomorrow.io/v4/weather"


def _build_base_params(latitude: float, longitude: float, api_key: Optional[str]) -> dict[str, str]:
    params = {
        "location": f"{latitude},{longitude}",
        "units": "metric",
    }
    if api_key:
        params["apikey"] = api_key
    return params


def fetch_tomorrow_io_observation(
    *,
    latitude: float,
    longitude: float,
    client: httpx.Client,
    api_key: Optional[str] = None,
    base_url: str = BASE_URL,
    retries: int = 2,
    timeout: Optional[httpx.Timeout] | float | None = DEFAULT_TIMEOUT,
):
    """Fetch a realtime observation and normalize it."""

    request = client.build_request(
        "GET",
        f"{base_url}/realtime",
        params=_build_base_params(latitude, longitude, api_key),
        headers={"accept": "application/json"},
        timeout=timeout,
    )
    response = send_with_retries(
        client,
        request,
        provider="tomorrow_io",
        operation="observation",
        retries=retries,
    )

    try:
        payload = response.json()
    except (ValueError, httpx.HTTPError) as exc:
        raise ProviderPayloadError("tomorrow_io", "observation", "Invalid JSON payload") from exc

    try:
        return map_tomorrow_io_observation(payload)
    except ValueError as exc:
        raise ProviderPayloadError("tomorrow_io", "observation", str(exc)) from exc


def fetch_tomorrow_io_forecast(
    *,
    latitude: float,
    longitude: float,
    client: httpx.Client,
    api_key: Optional[str] = None,
    base_url: str = BASE_URL,
    retries: int = 2,
    timeout: Optional[httpx.Timeout] | float | None = DEFAULT_TIMEOUT,
    timesteps: str = "1h",
):
    """Fetch forecast timelines and normalize them."""

    params = _build_base_params(latitude, longitude, api_key)
    params["timesteps"] = timesteps

    request = client.build_request(
        "GET",
        f"{base_url}/forecast",
        params=params,
        headers={"accept": "application/json"},
        timeout=timeout,
    )
    response = send_with_retries(
        client,
        request,
        provider="tomorrow_io",
        operation="forecast",
        retries=retries,
    )

    try:
        payload = response.json()
    except (ValueError, httpx.HTTPError) as exc:
        raise ProviderPayloadError("tomorrow_io", "forecast", "Invalid JSON payload") from exc

    try:
        return map_tomorrow_io_forecast(payload)
    except ValueError as exc:
        raise ProviderPayloadError("tomorrow_io", "forecast", str(exc)) from exc
