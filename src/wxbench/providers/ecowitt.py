"""Adapter for EcoWitt Cloud observations (station ground truth)."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Callable, Optional

import httpx
from pydantic import ValidationError

from wxbench.domain.mappers.ecowitt import map_ecowitt_realtime
from wxbench.domain.models import Location, Observation
from wxbench.providers._http import DEFAULT_TIMEOUT, send_with_retries
from wxbench.providers.capture import CapturedPayload, capture_payload
from wxbench.providers.errors import ProviderPayloadError
from wxbench.providers.schemas import EcowittRealtimePayload

__all__ = ["fetch_ecowitt_observation"]


BASE_URL = "https://api.ecowitt.net/api/v3"


def fetch_ecowitt_observation(
    *,
    client: httpx.Client,
    api_key: str,
    application_key: str,
    device_mac: str,
    location: Location,
    station: str | None = None,
    base_url: str = BASE_URL,
    retries: int = 2,
    timeout: Optional[httpx.Timeout] | float | None = DEFAULT_TIMEOUT,
    capture: Optional[Callable[[CapturedPayload], None]] = None,
) -> Observation:
    """Fetch the latest real-time observation from EcoWitt Cloud."""

    request = client.build_request(
        "GET",
        f"{base_url}/device/real_time",
        params={
            "application_key": application_key,
            "api_key": api_key,
            "mac": device_mac,
            "call_back": "all",
        },
        headers={"accept": "application/json"},
        timeout=timeout,
    )
    response = send_with_retries(
        client,
        request,
        provider="ecowitt",
        operation="observation",
        retries=retries,
    )

    payload_text = response.text
    if capture is not None:
        capture(
            capture_payload(
                provider="ecowitt",
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
        raise ProviderPayloadError("ecowitt", "observation", "Invalid JSON payload") from exc

    api_code = payload.get("code") if isinstance(payload, dict) else None
    if api_code is not None and api_code != 0:
        api_msg = payload.get("msg", "unknown error") if isinstance(payload, dict) else "unknown error"
        raise ProviderPayloadError("ecowitt", "observation", f"API error code {api_code}: {api_msg}")

    try:
        EcowittRealtimePayload.model_validate(payload)
    except ValidationError as exc:
        raise ProviderPayloadError("ecowitt", "observation", "Unexpected payload shape") from exc

    try:
        return map_ecowitt_realtime(
            payload,
            location=location,
            station=station,
            provider="ecowitt",
            capture_time_utc=datetime.now(timezone.utc),
        )
    except ValueError as exc:
        raise ProviderPayloadError("ecowitt", "observation", str(exc)) from exc

