"""Helpers for capturing raw provider exchanges."""
from __future__ import annotations

from datetime import datetime
from dataclasses import dataclass
from typing import Mapping

import httpx


_SENSITIVE_QUERY_KEYS = {
    "appid",
    "apikey",
    "apiKey",
    "applicationKey",
    "key",
    "token",
}

_SENSITIVE_HEADER_KEYS = {
    "authorization",
    "x-api-key",
}


@dataclass(frozen=True)
class CapturedPayload:
    """Redacted metadata + raw payload text from a provider response."""

    provider: str
    endpoint: str
    run_at: datetime
    request_url: str
    request_params: Mapping[str, str]
    request_headers: Mapping[str, str]
    response_status: int
    response_headers: Mapping[str, str]
    payload_text: str


def capture_payload(
    *,
    provider: str,
    endpoint: str,
    run_at: datetime,
    request: httpx.Request,
    response: httpx.Response,
    payload_text: str,
) -> CapturedPayload:
    """Create a redacted capture object for storage."""

    return CapturedPayload(
        provider=provider,
        endpoint=endpoint,
        run_at=run_at,
        request_url=str(request.url.copy_with(params=None)),
        request_params=_sanitize_params(request.url.params),
        request_headers=_sanitize_headers(request.headers),
        response_status=response.status_code,
        response_headers=_sanitize_headers(response.headers),
        payload_text=payload_text,
    )


def _sanitize_params(params: httpx.QueryParams) -> dict[str, str]:
    cleaned: dict[str, str] = {}
    for key, value in params.multi_items():
        if key in _SENSITIVE_QUERY_KEYS:
            cleaned[key] = "REDACTED"
        else:
            cleaned[key] = value
    return cleaned


def _sanitize_headers(headers: Mapping[str, str]) -> dict[str, str]:
    cleaned: dict[str, str] = {}
    for key, value in headers.items():
        if key.lower() in _SENSITIVE_HEADER_KEYS:
            cleaned[key] = "REDACTED"
        else:
            cleaned[key] = value
    return cleaned


__all__ = ["CapturedPayload", "capture_payload"]
