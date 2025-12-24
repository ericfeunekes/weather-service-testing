"""Shared HTTP helpers for provider adapters."""
from __future__ import annotations

from typing import Callable, Optional

import time

import httpx

from wxbench.providers.errors import (
    ProviderAuthError,
    ProviderRateLimitError,
    ProviderRequestError,
    ProviderTransientError,
)

__all__ = ["DEFAULT_TIMEOUT", "send_with_retries"]


DEFAULT_TIMEOUT = httpx.Timeout(10.0, connect=5.0)


def send_with_retries(
    client: httpx.Client,
    request: httpx.Request,
    *,
    provider: str,
    operation: str,
    retries: int = 2,
    backoff_seconds: float = 0.25,
    backoff_cap_seconds: float = 10.0,
    retry_after_cap_seconds: float = 30.0,
    sleep: Callable[[float], None] = time.sleep,
) -> httpx.Response:
    """Send a request with bounded retries and clear error classification."""

    def _backoff_delay(attempt_number: int) -> float:
        return min(backoff_seconds * (2**attempt_number), backoff_cap_seconds)

    def _retry_after_delay(response: httpx.Response) -> Optional[float]:
        header = response.headers.get("Retry-After")
        if header is None:
            return None

        try:
            delay = float(header)
        except ValueError:
            return None

        return min(delay, retry_after_cap_seconds)

    for attempt in range(retries + 1):
        try:
            response = client.send(request)
        except (httpx.TimeoutException, httpx.TransportError) as exc:
            if attempt < retries:
                sleep(_backoff_delay(attempt))
                continue
            raise ProviderTransientError(provider, operation, str(exc)) from exc

        status = response.status_code
        retry_after = _retry_after_delay(response)

        if status in (401, 403):
            raise ProviderAuthError(provider, operation, f"received status {status}")

        if status == 429:
            if attempt < retries:
                sleep(retry_after or _backoff_delay(attempt))
                continue
            raise ProviderRateLimitError(provider, operation, "rate limit exceeded")

        if status == 408 or 500 <= status < 600:
            if attempt < retries:
                delay = retry_after if status == 503 and retry_after is not None else _backoff_delay(attempt)
                sleep(delay)
                continue
            raise ProviderTransientError(provider, operation, f"upstream error {status}")

        if 400 <= status < 500:
            raise ProviderRequestError(provider, operation, f"request failed with status {status}")

        try:
            response.raise_for_status()
            return response
        except httpx.HTTPError as exc:  # pragma: no cover - defensive guard
            raise ProviderTransientError(provider, operation, str(exc)) from exc

    raise ProviderTransientError(provider, operation, "retries exhausted")
