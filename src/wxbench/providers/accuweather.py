"""Adapter for AccuWeather APIs."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Callable, Optional

import httpx
from pydantic import ValidationError

from wxbench.domain.mappers.accuweather import (
    AccuweatherLocation,
    map_accuweather_daily_forecast,
    map_accuweather_hourly_forecast,
    map_accuweather_location,
    map_accuweather_minute_forecast,
    map_accuweather_observation,
)
from wxbench.providers.capture import CapturedPayload, capture_payload
from wxbench.providers._http import DEFAULT_TIMEOUT, send_with_retries
from wxbench.providers.errors import ProviderPayloadError
from wxbench.providers.schemas import (
    AccuCurrentConditionsPayload,
    AccuDailyForecastPayload,
    AccuHourlyForecastPayload,
    AccuLocationPayload,
)

__all__ = [
    "fetch_accuweather_location",
    "fetch_accuweather_observation",
    "fetch_accuweather_hourly_forecast",
    "fetch_accuweather_daily_forecast",
    "fetch_accuweather_minute_forecast",
]

BASE_URL = "https://dataservice.accuweather.com"


def _format_location(latitude: float, longitude: float) -> str:
    return f"{latitude},{longitude}"


def _default_clock() -> datetime:
    return datetime.now(tz=timezone.utc)


def fetch_accuweather_minute_forecast(
    *,
    latitude: float,
    longitude: float,
    client: httpx.Client,
    api_key: Optional[str] = None,
    base_url: str = BASE_URL,
    details: bool = False,
    language: Optional[str] = None,
    retries: int = 2,
    timeout: Optional[httpx.Timeout] | float | None = DEFAULT_TIMEOUT,
    clock: Optional[Callable[[], datetime]] = None,
    capture: Optional[Callable[[CapturedPayload], None]] = None,
):
    """Fetch minute-by-minute forecast intervals and normalize them."""

    now = (clock or _default_clock)()
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    params: dict[str, str] = {
        "q": _format_location(latitude, longitude),
    }
    if details:
        params["details"] = "true"
    if language:
        params["language"] = language

    headers = {"accept": "application/json"}
    if api_key:
        headers["authorization"] = f"Bearer {api_key}"

    request = client.build_request(
        "GET",
        f"{base_url}/forecasts/v1/minute",
        params=params,
        headers=headers,
        timeout=timeout,
    )
    response = send_with_retries(
        client,
        request,
        provider="accuweather",
        operation="minute_forecast",
        retries=retries,
    )

    payload_text = response.text
    if capture is not None:
        capture(
            capture_payload(
                provider="accuweather",
                endpoint="minute_forecast",
                run_at=now,
                request=request,
                response=response,
                payload_text=payload_text,
            )
        )

    try:
        payload = response.json()
    except (ValueError, httpx.HTTPError) as exc:
        raise ProviderPayloadError("accuweather", "minute_forecast", "Invalid JSON payload") from exc

    try:
        return map_accuweather_minute_forecast(payload, latitude=latitude, longitude=longitude, issued_at=now)
    except ValueError as exc:
        raise ProviderPayloadError("accuweather", "minute_forecast", str(exc)) from exc


def fetch_accuweather_location(
    *,
    latitude: float,
    longitude: float,
    client: httpx.Client,
    api_key: Optional[str] = None,
    base_url: str = BASE_URL,
    retries: int = 2,
    timeout: Optional[httpx.Timeout] | float | None = DEFAULT_TIMEOUT,
    capture: Optional[Callable[[CapturedPayload], None]] = None,
) -> AccuweatherLocation:
    """Fetch a location key for the given coordinates."""

    params = {"q": _format_location(latitude, longitude)}
    if api_key:
        params["apikey"] = api_key

    request = client.build_request(
        "GET",
        f"{base_url}/locations/v1/cities/geoposition/search",
        params=params,
        headers={"accept": "application/json"},
        timeout=timeout,
    )
    response = send_with_retries(
        client,
        request,
        provider="accuweather",
        operation="location_search",
        retries=retries,
    )

    payload_text = response.text
    if capture is not None:
        capture(
            capture_payload(
                provider="accuweather",
                endpoint="location_search",
                run_at=datetime.now(timezone.utc),
                request=request,
                response=response,
                payload_text=payload_text,
            )
        )

    try:
        payload = response.json()
    except (ValueError, httpx.HTTPError) as exc:
        raise ProviderPayloadError("accuweather", "location_search", "Invalid JSON payload") from exc
    try:
        AccuLocationPayload.model_validate(payload)
    except ValidationError as exc:
        raise ProviderPayloadError("accuweather", "location_search", "Unexpected payload shape") from exc

    try:
        return map_accuweather_location(payload)
    except ValueError as exc:
        raise ProviderPayloadError("accuweather", "location_search", str(exc)) from exc


def fetch_accuweather_observation(
    *,
    location_key: str,
    latitude: float,
    longitude: float,
    client: httpx.Client,
    api_key: Optional[str] = None,
    base_url: str = BASE_URL,
    details: bool = True,
    retries: int = 2,
    timeout: Optional[httpx.Timeout] | float | None = DEFAULT_TIMEOUT,
    capture: Optional[Callable[[CapturedPayload], None]] = None,
):
    """Fetch current conditions and normalize them."""

    params: dict[str, str] = {}
    if api_key:
        params["apikey"] = api_key
    if details:
        params["details"] = "true"

    request = client.build_request(
        "GET",
        f"{base_url}/currentconditions/v1/{location_key}",
        params=params,
        headers={"accept": "application/json"},
        timeout=timeout,
    )
    response = send_with_retries(
        client,
        request,
        provider="accuweather",
        operation="observation",
        retries=retries,
    )

    payload_text = response.text
    if capture is not None:
        capture(
            capture_payload(
                provider="accuweather",
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
        raise ProviderPayloadError("accuweather", "observation", "Invalid JSON payload") from exc
    try:
        AccuCurrentConditionsPayload.model_validate(payload)
    except ValidationError as exc:
        raise ProviderPayloadError("accuweather", "observation", "Unexpected payload shape") from exc

    try:
        return map_accuweather_observation(payload, latitude=latitude, longitude=longitude)
    except ValueError as exc:
        raise ProviderPayloadError("accuweather", "observation", str(exc)) from exc


def fetch_accuweather_hourly_forecast(
    *,
    location_key: str,
    latitude: float,
    longitude: float,
    client: httpx.Client,
    api_key: Optional[str] = None,
    base_url: str = BASE_URL,
    details: bool = True,
    retries: int = 2,
    timeout: Optional[httpx.Timeout] | float | None = DEFAULT_TIMEOUT,
    capture: Optional[Callable[[CapturedPayload], None]] = None,
):
    """Fetch 12-hour hourly forecasts and normalize them."""

    params: dict[str, str] = {"metric": "true"}
    if api_key:
        params["apikey"] = api_key
    if details:
        params["details"] = "true"

    request = client.build_request(
        "GET",
        f"{base_url}/forecasts/v1/hourly/12hour/{location_key}",
        params=params,
        headers={"accept": "application/json"},
        timeout=timeout,
    )
    response = send_with_retries(
        client,
        request,
        provider="accuweather",
        operation="forecast_hourly",
        retries=retries,
    )

    payload_text = response.text
    if capture is not None:
        capture(
            capture_payload(
                provider="accuweather",
                endpoint="forecast_hourly",
                run_at=datetime.now(timezone.utc),
                request=request,
                response=response,
                payload_text=payload_text,
            )
        )

    try:
        payload = response.json()
    except (ValueError, httpx.HTTPError) as exc:
        raise ProviderPayloadError("accuweather", "forecast_hourly", "Invalid JSON payload") from exc
    try:
        AccuHourlyForecastPayload.model_validate(payload)
    except ValidationError as exc:
        raise ProviderPayloadError("accuweather", "forecast_hourly", "Unexpected payload shape") from exc

    try:
        return map_accuweather_hourly_forecast(payload, latitude=latitude, longitude=longitude)
    except ValueError as exc:
        raise ProviderPayloadError("accuweather", "forecast_hourly", str(exc)) from exc


def fetch_accuweather_daily_forecast(
    *,
    location_key: str,
    latitude: float,
    longitude: float,
    client: httpx.Client,
    api_key: Optional[str] = None,
    base_url: str = BASE_URL,
    details: bool = True,
    retries: int = 2,
    timeout: Optional[httpx.Timeout] | float | None = DEFAULT_TIMEOUT,
    capture: Optional[Callable[[CapturedPayload], None]] = None,
):
    """Fetch 5-day daily forecasts and normalize them."""

    params: dict[str, str] = {"metric": "true"}
    if api_key:
        params["apikey"] = api_key
    if details:
        params["details"] = "true"

    request = client.build_request(
        "GET",
        f"{base_url}/forecasts/v1/daily/5day/{location_key}",
        params=params,
        headers={"accept": "application/json"},
        timeout=timeout,
    )
    response = send_with_retries(
        client,
        request,
        provider="accuweather",
        operation="forecast_daily",
        retries=retries,
    )

    payload_text = response.text
    if capture is not None:
        capture(
            capture_payload(
                provider="accuweather",
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
        raise ProviderPayloadError("accuweather", "forecast_daily", "Invalid JSON payload") from exc
    try:
        AccuDailyForecastPayload.model_validate(payload)
    except ValidationError as exc:
        raise ProviderPayloadError("accuweather", "forecast_daily", "Unexpected payload shape") from exc

    try:
        return map_accuweather_daily_forecast(payload, latitude=latitude, longitude=longitude)
    except ValueError as exc:
        raise ProviderPayloadError("accuweather", "forecast_daily", str(exc)) from exc
