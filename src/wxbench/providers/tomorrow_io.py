"""Adapter for Tomorrow.io Weather API."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Callable, Optional

import httpx
from pydantic import ValidationError

from wxbench.domain.mappers.tomorrow_io import (
    map_tomorrow_io_daily_forecast,
    map_tomorrow_io_forecast,
    map_tomorrow_io_observation,
)
from wxbench.providers.capture import CapturedPayload, capture_payload
from wxbench.providers._http import DEFAULT_TIMEOUT, send_with_retries
from wxbench.providers.errors import ProviderPayloadError
from wxbench.providers.schemas import TomorrowForecastPayload, TomorrowRealtimePayload

__all__ = [
    "fetch_tomorrow_io_forecast",
    "fetch_tomorrow_io_daily_forecast",
    "fetch_tomorrow_io_observation",
]


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
    capture: Optional[Callable[[CapturedPayload], None]] = None,
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

    payload_text = response.text
    if capture is not None:
        capture(
            capture_payload(
                provider="tomorrow_io",
                endpoint="observation",
                run_at=datetime.now(timezone.utc),
                request=request,
                response=response,
                payload_text=payload_text,
            )
        )

    try:
        payload = response.json()
    except (ValueError, httpx.HTTPError) as exc:
        raise ProviderPayloadError("tomorrow_io", "observation", "Invalid JSON payload") from exc
    try:
        TomorrowRealtimePayload.model_validate(payload)
    except ValidationError as exc:
        raise ProviderPayloadError("tomorrow_io", "observation", "Unexpected payload shape") from exc

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
    capture: Optional[Callable[[CapturedPayload], None]] = None,
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

    payload_text = response.text
    if capture is not None:
        capture(
            capture_payload(
                provider="tomorrow_io",
                endpoint="forecast",
                run_at=datetime.now(timezone.utc),
                request=request,
                response=response,
                payload_text=payload_text,
            )
        )

    try:
        payload = response.json()
    except (ValueError, httpx.HTTPError) as exc:
        raise ProviderPayloadError("tomorrow_io", "forecast", "Invalid JSON payload") from exc
    try:
        TomorrowForecastPayload.model_validate(payload)
    except ValidationError as exc:
        raise ProviderPayloadError("tomorrow_io", "forecast", "Unexpected payload shape") from exc

    try:
        return map_tomorrow_io_forecast(payload)
    except ValueError as exc:
        raise ProviderPayloadError("tomorrow_io", "forecast", str(exc)) from exc


def fetch_tomorrow_io_daily_forecast(
    *,
    latitude: float,
    longitude: float,
    client: httpx.Client,
    api_key: Optional[str] = None,
    base_url: str = BASE_URL,
    retries: int = 2,
    timeout: Optional[httpx.Timeout] | float | None = DEFAULT_TIMEOUT,
    capture: Optional[Callable[[CapturedPayload], None]] = None,
):
    """Fetch daily forecast timelines and normalize them."""

    params = _build_base_params(latitude, longitude, api_key)
    params["timesteps"] = "1d"

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
        operation="forecast_daily",
        retries=retries,
    )

    payload_text = response.text
    if capture is not None:
        capture(
            capture_payload(
                provider="tomorrow_io",
                endpoint="forecast_daily",
                run_at=datetime.now(timezone.utc),
                request=request,
                response=response,
                payload_text=payload_text,
            )
        )

    try:
        payload = response.json()
    except (ValueError, httpx.HTTPError) as exc:
        raise ProviderPayloadError("tomorrow_io", "forecast_daily", "Invalid JSON payload") from exc
    try:
        TomorrowForecastPayload.model_validate(payload)
    except ValidationError as exc:
        raise ProviderPayloadError("tomorrow_io", "forecast_daily", "Unexpected payload shape") from exc

    try:
        return map_tomorrow_io_daily_forecast(payload)
    except ValueError as exc:
        raise ProviderPayloadError("tomorrow_io", "forecast_daily", str(exc)) from exc
