"""Adapter for OpenWeather API."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Callable, Optional

import httpx
from pydantic import ValidationError

from wxbench.domain.mappers.openweather import (
    map_openweather_forecast,
    map_openweather_observation,
    map_openweather_onecall_daily,
    map_openweather_onecall_hourly,
)
from wxbench.providers.schemas import (
    OpenWeatherForecastPayload,
    OpenWeatherObservationPayload,
    OpenWeatherOneCallPayload,
)
from wxbench.providers.capture import CapturedPayload, capture_payload
from wxbench.providers._http import DEFAULT_TIMEOUT, send_with_retries
from wxbench.providers.errors import ProviderPayloadError

__all__ = [
    "fetch_openweather_forecast",
    "fetch_openweather_observation",
    "fetch_openweather_onecall_daily",
    "fetch_openweather_onecall_hourly",
]


BASE_URL = "https://api.openweathermap.org/data/2.5"
ONECALL_BASE_URL = "https://api.openweathermap.org/data/3.0"


def _build_common_params(latitude: float, longitude: float, api_key: Optional[str]) -> dict[str, str]:
    params = {"lat": str(latitude), "lon": str(longitude)}
    if api_key:
        params["appid"] = api_key
    return params


def _build_onecall_params(latitude: float, longitude: float, api_key: Optional[str]) -> dict[str, str]:
    params = _build_common_params(latitude, longitude, api_key)
    params["units"] = "metric"
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
    capture: Optional[Callable[[CapturedPayload], None]] = None,
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

    payload_text = response.text
    if capture is not None:
        capture(
            capture_payload(
                provider="openweather",
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
        raise ProviderPayloadError("openweather", "observation", "Invalid JSON payload") from exc
    try:
        OpenWeatherObservationPayload.model_validate(payload)
    except ValidationError as exc:
        raise ProviderPayloadError("openweather", "observation", "Unexpected payload shape") from exc

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
    capture: Optional[Callable[[CapturedPayload], None]] = None,
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

    payload_text = response.text
    if capture is not None:
        capture(
            capture_payload(
                provider="openweather",
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
        raise ProviderPayloadError("openweather", "forecast", "Invalid JSON payload") from exc
    try:
        OpenWeatherForecastPayload.model_validate(payload)
    except ValidationError as exc:
        raise ProviderPayloadError("openweather", "forecast", "Unexpected payload shape") from exc

    try:
        return map_openweather_forecast(payload)
    except ValueError as exc:
        raise ProviderPayloadError("openweather", "forecast", str(exc)) from exc


def fetch_openweather_onecall_hourly(
    *,
    latitude: float,
    longitude: float,
    client: httpx.Client,
    api_key: Optional[str] = None,
    base_url: str = ONECALL_BASE_URL,
    retries: int = 2,
    timeout: Optional[httpx.Timeout] | float | None = DEFAULT_TIMEOUT,
    capture: Optional[Callable[[CapturedPayload], None]] = None,
):
    """Fetch One Call hourly forecast and normalize it."""

    params = _build_onecall_params(latitude, longitude, api_key)
    params["exclude"] = "minutely,daily,alerts,current"

    request = client.build_request(
        "GET",
        f"{base_url}/onecall",
        params=params,
        headers={"accept": "application/json"},
        timeout=timeout,
    )
    response = send_with_retries(
        client,
        request,
        provider="openweather",
        operation="onecall_hourly",
        retries=retries,
    )

    payload_text = response.text
    if capture is not None:
        capture(
            capture_payload(
                provider="openweather",
                endpoint="onecall_hourly",
                run_at=datetime.now(timezone.utc),
                request=request,
                response=response,
                payload_text=payload_text,
            )
        )

    try:
        payload = response.json()
    except (ValueError, httpx.HTTPError) as exc:
        raise ProviderPayloadError("openweather", "onecall_hourly", "Invalid JSON payload") from exc
    try:
        OpenWeatherOneCallPayload.model_validate(payload)
    except ValidationError as exc:
        raise ProviderPayloadError("openweather", "onecall_hourly", "Unexpected payload shape") from exc

    try:
        return map_openweather_onecall_hourly(payload)
    except ValueError as exc:
        raise ProviderPayloadError("openweather", "onecall_hourly", str(exc)) from exc


def fetch_openweather_onecall_daily(
    *,
    latitude: float,
    longitude: float,
    client: httpx.Client,
    api_key: Optional[str] = None,
    base_url: str = ONECALL_BASE_URL,
    retries: int = 2,
    timeout: Optional[httpx.Timeout] | float | None = DEFAULT_TIMEOUT,
    capture: Optional[Callable[[CapturedPayload], None]] = None,
):
    """Fetch One Call daily forecast and normalize it."""

    params = _build_onecall_params(latitude, longitude, api_key)
    params["exclude"] = "minutely,hourly,alerts,current"

    request = client.build_request(
        "GET",
        f"{base_url}/onecall",
        params=params,
        headers={"accept": "application/json"},
        timeout=timeout,
    )
    response = send_with_retries(
        client,
        request,
        provider="openweather",
        operation="onecall_daily",
        retries=retries,
    )

    payload_text = response.text
    if capture is not None:
        capture(
            capture_payload(
                provider="openweather",
                endpoint="onecall_daily",
                run_at=datetime.now(timezone.utc),
                request=request,
                response=response,
                payload_text=payload_text,
            )
        )

    try:
        payload = response.json()
    except (ValueError, httpx.HTTPError) as exc:
        raise ProviderPayloadError("openweather", "onecall_daily", "Invalid JSON payload") from exc
    try:
        OpenWeatherOneCallPayload.model_validate(payload)
    except ValidationError as exc:
        raise ProviderPayloadError("openweather", "onecall_daily", "Unexpected payload shape") from exc

    try:
        return map_openweather_onecall_daily(payload)
    except ValueError as exc:
        raise ProviderPayloadError("openweather", "onecall_daily", str(exc)) from exc
