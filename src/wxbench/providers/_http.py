"""Shared HTTP helpers for provider adapters."""
from __future__ import annotations

import time

import httpx

__all__ = ["DEFAULT_TIMEOUT", "send_with_retries"]


DEFAULT_TIMEOUT = httpx.Timeout(10.0, connect=5.0)


def send_with_retries(
    client: httpx.Client,
    request: httpx.Request,
    *,
    retries: int = 2,
    backoff_seconds: float = 0.25,
) -> httpx.Response:
    """Send a request with simple bounded retries.

    This helper keeps retry policy and timeout selection in one place so each
    provider adapter can remain a thin boundary around the mapping logic. Only
    transient failures (5xx, timeouts, transport errors) are retried.
    """

    for attempt in range(retries + 1):
        try:
            response = client.send(request)
            response.raise_for_status()
            return response
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            if status >= 500 and attempt < retries:
                time.sleep(backoff_seconds * (2**attempt))
                continue
            raise
        except (httpx.TimeoutException, httpx.TransportError):
            if attempt < retries:
                time.sleep(backoff_seconds * (2**attempt))
                continue
            raise

    # Should be unreachable because either a response is returned or an
    # exception is raised inside the loop.
    raise RuntimeError("Request retries exhausted")
