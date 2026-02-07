"""Adapter for Apple WeatherKit REST API."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, Iterable, Optional

import httpx
from pydantic import ValidationError

from wxbench.domain.mappers.weatherkit import (
    map_weatherkit_daily_forecast,
    map_weatherkit_hourly_forecast,
    map_weatherkit_next_hour_forecast,
    map_weatherkit_observation,
    map_weatherkit_alerts,
)
from wxbench.domain.models import ForecastPeriod, Observation, WeatherAlert
from wxbench.providers.capture import CapturedPayload, capture_payload
from wxbench.providers._http import DEFAULT_TIMEOUT, send_with_retries
from wxbench.providers.errors import ProviderPayloadError
from wxbench.providers.schemas import WeatherKitWeatherPayload
from wxbench.providers.weatherkit_auth import build_weatherkit_token

__all__ = ["WeatherKitBundle", "fetch_weatherkit_bundle"]


BASE_URL = "https://weatherkit.apple.com"
DEFAULT_LANGUAGE = "en-US"
DEFAULT_DATASETS = ("currentWeather", "forecastHourly", "forecastDaily", "forecastNextHour")


@dataclass(frozen=True)
class WeatherKitBundle:
    observation: Optional[Observation]
    hourly: list[ForecastPeriod]
    daily: list[ForecastPeriod]
    next_hour: list[ForecastPeriod]
    alerts: list[WeatherAlert]


def _dataset_param(datasets: Iterable[str]) -> str:
    return ",".join(datasets)


def _normalize_datasets(datasets: Iterable[str], *, country_code: Optional[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for item in datasets:
        if item and item not in seen:
            seen.add(item)
            ordered.append(item)
    if country_code:
        if "weatherAlerts" not in seen:
            ordered.append("weatherAlerts")
    else:
        ordered = [item for item in ordered if item != "weatherAlerts"]
    return ordered


def fetch_weatherkit_bundle(
    *,
    latitude: float,
    longitude: float,
    timezone_name: str,
    client: httpx.Client,
    team_id: str,
    service_id: str,
    key_id: str,
    key_path: str,
    country_code: Optional[str] = None,
    language: str = DEFAULT_LANGUAGE,
    datasets: Iterable[str] = DEFAULT_DATASETS,
    base_url: str = BASE_URL,
    retries: int = 2,
    timeout: Optional[httpx.Timeout] | float | None = DEFAULT_TIMEOUT,
    token_ttl_seconds: int = 3600,
    capture: Optional[Callable[[CapturedPayload], None]] = None,
) -> WeatherKitBundle:
    """Fetch WeatherKit data for a location and normalize it."""

    token = build_weatherkit_token(
        team_id=team_id,
        service_id=service_id,
        key_id=key_id,
        key_path=key_path,
        ttl_seconds=token_ttl_seconds,
    )

    dataset_list = _normalize_datasets(datasets, country_code=country_code)

    request = client.build_request(
        "GET",
        f"{base_url}/api/v1/weather/{language}/{latitude}/{longitude}",
        params={
            "dataSets": _dataset_param(dataset_list),
            "timezone": timezone_name,
            **({"countryCode": country_code} if country_code else {}),
        },
        headers={"authorization": f"Bearer {token}", "accept": "application/json"},
        timeout=timeout,
    )

    response = send_with_retries(
        client,
        request,
        provider="weatherkit",
        operation="weather",
        retries=retries,
    )

    payload_text = response.text
    if capture is not None:
        capture(
            capture_payload(
                provider="weatherkit",
                endpoint="weather",
                run_at=datetime.now(timezone.utc),
                request=request,
                response=response,
                payload_text=payload_text,
            )
        )

    try:
        payload = response.json()
    except (ValueError, httpx.HTTPError) as exc:
        raise ProviderPayloadError("weatherkit", "weather", "Invalid JSON payload") from exc
    try:
        WeatherKitWeatherPayload.model_validate(payload)
    except ValidationError as exc:
        raise ProviderPayloadError("weatherkit", "weather", "Unexpected payload shape") from exc

    observation: Optional[Observation] = None
    if payload.get("currentWeather") is not None:
        observation = map_weatherkit_observation(payload)

    hourly: list[ForecastPeriod] = []
    if payload.get("forecastHourly") is not None:
        hourly = map_weatherkit_hourly_forecast(payload)

    daily: list[ForecastPeriod] = []
    if payload.get("forecastDaily") is not None:
        daily = map_weatherkit_daily_forecast(payload)

    next_hour: list[ForecastPeriod] = []
    if payload.get("forecastNextHour") is not None:
        next_hour = map_weatherkit_next_hour_forecast(payload)

    alerts: list[WeatherAlert] = []
    if payload.get("weatherAlerts") is not None:
        alerts = map_weatherkit_alerts(payload)

    return WeatherKitBundle(
        observation=observation,
        hourly=hourly,
        daily=daily,
        next_hour=next_hour,
        alerts=alerts,
    )
