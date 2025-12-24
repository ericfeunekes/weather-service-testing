"""Adapter for OpenWeather API."""
from __future__ import annotations

from typing import Optional

import httpx

from wxbench.domain.mappers.openweather import map_openweather_forecast, map_openweather_observation
from wxbench.providers._http import DEFAULT_TIMEOUT, send_with_retries
from wxbench.providers.errors import ProviderPayloadError

__all__ = ["fetch_openweather_forecast", "fetch_openweather_observation"]


BASE_URL = "https://api.openweathermap.org/data/2.5"


def _build_common_params(latitude: float, longitude: float, api_key: Optional[str]) -> dict[str, str]:
    params = {"lat": str(latitude), "lon": str(longitude)}
    if api_key:
        params["appid"] = api_key
    return params


def fetch_openweather_observation(
    *,
    latitude: float,
    longitude: float,
    client: httpx.Client,
    api_key: Optional[str] = None,
    base_url: str = BASE_URL,
    retries: int = 2,
    timeout: Optional[httpx.Timeout] | float | None = DEFAULT_TIMEOUT,
):
    """Fetch the latest observation and map it to the domain model."""

    request = client.build_request(
        "GET",
        f"{base_url}/weather",
        params=_build_common_params(latitude, longitude, api_key),
        headers={"accept": "application/json"},
        timeout=timeout,
    )
    response = send_with_retries(
        client,
        request,
        provider="openweather",
        operation="observation",
        retries=retries,
    )

    try:
        payload = response.json()
    except (ValueError, httpx.HTTPError) as exc:
        raise ProviderPayloadError("openweather", "observation", "Invalid JSON payload") from exc

    try:
        return map_openweather_observation(payload)
    except ValueError as exc:
        raise ProviderPayloadError("openweather", "observation", str(exc)) from exc


def fetch_openweather_forecast(
    *,
    latitude: float,
    longitude: float,
    client: httpx.Client,
    api_key: Optional[str] = None,
    base_url: str = BASE_URL,
    retries: int = 2,
    timeout: Optional[httpx.Timeout] | float | None = DEFAULT_TIMEOUT,
):
    """Fetch the forecast and map it to normalized periods."""

    request = client.build_request(
        "GET",
        f"{base_url}/forecast",
        params=_build_common_params(latitude, longitude, api_key),
        headers={"accept": "application/json"},
        timeout=timeout,
    )
    response = send_with_retries(
        client,
        request,
        provider="openweather",
        operation="forecast",
        retries=retries,
    )

    try:
        payload = response.json()
    except (ValueError, httpx.HTTPError) as exc:
        raise ProviderPayloadError("openweather", "forecast", "Invalid JSON payload") from exc

    try:
        return map_openweather_forecast(payload)
    except ValueError as exc:
        raise ProviderPayloadError("openweather", "forecast", str(exc)) from exc
