"""Shared error taxonomy for provider boundaries."""
from __future__ import annotations

from dataclasses import dataclass

__all__ = [
    "ProviderError",
    "ProviderAuthError",
    "ProviderRateLimitError",
    "ProviderTransientError",
    "ProviderRequestError",
    "ProviderPayloadError",
]


@dataclass
class ProviderError(Exception):
    """Base provider error with contextual metadata."""

    provider: str
    operation: str
    message: str

    def __str__(self) -> str:  # pragma: no cover - simple representation
        return f"{self.provider}:{self.operation}: {self.message}"


class ProviderAuthError(ProviderError):
    """Authentication or authorization failure."""


class ProviderRateLimitError(ProviderError):
    """Provider rate limit encountered."""


class ProviderTransientError(ProviderError):
    """Transient upstream failure after retries."""


class ProviderRequestError(ProviderError):
    """Non-auth 4xx request failure."""


class ProviderPayloadError(ProviderError):
    """Payload decoding or mapping failure."""

