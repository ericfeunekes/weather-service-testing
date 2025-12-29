"""Adapter for Environment Canada MSC GeoMet API."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Callable, Optional

import httpx
from pydantic import ValidationError

from wxbench.domain.mappers.msc_geomet import map_msc_geomet_forecast, map_msc_geomet_observation
from wxbench.providers.capture import CapturedPayload, capture_payload
from wxbench.providers._http import DEFAULT_TIMEOUT, send_with_retries
from wxbench.providers.errors import ProviderPayloadError
from wxbench.providers.schemas import MscFeatureCollectionPayload

__all__ = ["fetch_msc_geomet_forecast", "fetch_msc_geomet_observation"]


BASE_URL = "https://api.weather.gc.ca/collections/citypageweather-realtime/items"


def _build_common_params(latitude: float, longitude: float, *, bbox_radius: float = 0.5) -> dict[str, str]:
    return {
        "bbox": f"{longitude - bbox_radius},{latitude - bbox_radius},{longitude + bbox_radius},{latitude + bbox_radius}",
        "limit": "1",
        "f": "json",
    }


def _extract_first_feature(payload: dict[str, object]) -> dict[str, object]:
    features = payload.get("features")
    if not isinstance(features, list) or not features:
        raise ProviderPayloadError("msc_geomet", "feature", "No features returned for coordinate")
    first = features[0]
    if not isinstance(first, dict):  # pragma: no cover - defensive
        raise ProviderPayloadError("msc_geomet", "feature", "Unexpected feature format")
    return first


def fetch_msc_geomet_observation(
    *,
    latitude: float,
    longitude: float,
    client: httpx.Client,
    base_url: str = BASE_URL,
    retries: int = 2,
    timeout: Optional[httpx.Timeout] | float | None = DEFAULT_TIMEOUT,
    capture: Optional[Callable[[CapturedPayload], None]] = None,
):
    """Fetch the latest observation feature for a coordinate pair."""

    request = client.build_request(
        "GET",
        base_url,
        params=_build_common_params(latitude, longitude),
        headers={"accept": "application/json"},
        timeout=timeout,
    )
    response = send_with_retries(
        client,
        request,
        provider="msc_geomet",
        operation="observation",
        retries=retries,
    )

    payload_text = response.text
    if capture is not None:
        capture(
            capture_payload(
                provider="msc_geomet",
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
        raise ProviderPayloadError("msc_geomet", "observation", "Invalid JSON payload") from exc
    try:
        MscFeatureCollectionPayload.model_validate(payload)
    except ValidationError as exc:
        raise ProviderPayloadError("msc_geomet", "observation", "Unexpected payload shape") from exc

    try:
        feature = _extract_first_feature(payload)
        return map_msc_geomet_observation(feature)
    except ValueError as exc:
        raise ProviderPayloadError("msc_geomet", "observation", str(exc)) from exc


def fetch_msc_geomet_forecast(
    *,
    latitude: float,
    longitude: float,
    client: httpx.Client,
    base_url: str = BASE_URL,
    retries: int = 2,
    timeout: Optional[httpx.Timeout] | float | None = DEFAULT_TIMEOUT,
    capture: Optional[Callable[[CapturedPayload], None]] = None,
):
    """Fetch forecast feature data for a coordinate pair."""

    request = client.build_request(
        "GET",
        base_url,
        params=_build_common_params(latitude, longitude),
        headers={"accept": "application/json"},
        timeout=timeout,
    )
    response = send_with_retries(
        client,
        request,
        provider="msc_geomet",
        operation="forecast",
        retries=retries,
    )

    payload_text = response.text
    if capture is not None:
        capture(
            capture_payload(
                provider="msc_geomet",
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
        raise ProviderPayloadError("msc_geomet", "forecast", "Invalid JSON payload") from exc
    try:
        MscFeatureCollectionPayload.model_validate(payload)
    except ValidationError as exc:
        raise ProviderPayloadError("msc_geomet", "forecast", "Unexpected payload shape") from exc

    try:
        feature = _extract_first_feature(payload)
        return map_msc_geomet_forecast(feature)
    except ValueError as exc:
        raise ProviderPayloadError("msc_geomet", "forecast", str(exc)) from exc
