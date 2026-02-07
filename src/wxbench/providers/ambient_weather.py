"""Adapter for AmbientWeather observations."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Callable, Optional

import httpx
from pydantic import ValidationError

from wxbench.domain.mappers.ambient_weather import (
    map_ambient_weather_history,
    map_ambient_weather_observation,
)
from wxbench.domain.models import Location, Observation
from wxbench.providers.capture import CapturedPayload, capture_payload
from wxbench.providers._http import DEFAULT_TIMEOUT, send_with_retries
from wxbench.providers.errors import ProviderPayloadError
from wxbench.providers.schemas import AmbientHistoryPayload, AmbientObservationPayload

__all__ = ["fetch_ambient_weather_observation", "fetch_ambient_weather_history"]


BASE_URL = "https://api.ambientweather.net/v1"


def fetch_ambient_weather_observation(
    *,
    client: httpx.Client,
    api_key: Optional[str] = None,
    application_key: Optional[str] = None,
    base_url: str = BASE_URL,
    retries: int = 2,
    timeout: Optional[httpx.Timeout] | float | None = DEFAULT_TIMEOUT,
    device_mac: Optional[str] = None,
    capture: Optional[Callable[[CapturedPayload], None]] = None,
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

    payload_text = response.text
    if capture is not None:
        capture(
            capture_payload(
                provider="ambient_weather",
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
        raise ProviderPayloadError("ambient_weather", "observation", "Invalid JSON payload") from exc
    try:
        AmbientObservationPayload.model_validate(payload)
    except ValidationError as exc:
        raise ProviderPayloadError("ambient_weather", "observation", "Unexpected payload shape") from exc

    try:
        return map_ambient_weather_observation(payload, device_mac=device_mac)
    except ValueError as exc:
        raise ProviderPayloadError("ambient_weather", "observation", str(exc)) from exc


def fetch_ambient_weather_history(
    *,
    client: httpx.Client,
    api_key: str,
    application_key: str,
    device_mac: str,
    location: Location,
    station: str | None,
    end_at: datetime,
    limit: int = 288,
    base_url: str = BASE_URL,
    retries: int = 2,
    timeout: Optional[httpx.Timeout] | float | None = DEFAULT_TIMEOUT,
    capture: Optional[Callable[[CapturedPayload], None]] = None,
) -> list[Observation]:
    """Fetch historical observations for a device."""

    end_date = int(end_at.timestamp() * 1000)
    request = client.build_request(
        "GET",
        f"{base_url}/devices/{device_mac}",
        params={
            "applicationKey": application_key,
            "apiKey": api_key,
            "limit": str(limit),
            "end_date": str(end_date),
        },
        headers={"accept": "application/json"},
        timeout=timeout,
    )
    response = send_with_retries(
        client,
        request,
        provider="ambient_weather",
        operation="history",
        retries=retries,
    )

    payload_text = response.text
    if capture is not None:
        capture(
            capture_payload(
                provider="ambient_weather",
                endpoint="history",
                run_at=datetime.now(timezone.utc),
                request=request,
                response=response,
                payload_text=payload_text,
            )
        )

    try:
        payload = response.json()
    except (ValueError, httpx.HTTPError) as exc:
        raise ProviderPayloadError("ambient_weather", "history", "Invalid JSON payload") from exc
    try:
        AmbientHistoryPayload.model_validate(payload)
    except ValidationError as exc:
        raise ProviderPayloadError("ambient_weather", "history", "Unexpected payload shape") from exc

    try:
        return map_ambient_weather_history(payload, location=location, station=station)
    except ValueError as exc:
        raise ProviderPayloadError("ambient_weather", "history", str(exc)) from exc
