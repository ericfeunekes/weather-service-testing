"""Runtime configuration parsing.

This module validates required environment variables for the configured
location and surfaces optional provider-specific secrets without introducing
hard dependencies on any given provider module. Validation is pure so it can be
exercised in unit tests without network or filesystem access.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Dict, Mapping
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

__all__ = ["ConfigError", "WxConfig", "load_config"]


class ConfigError(ValueError):
    """Raised when required configuration is missing or invalid."""


@dataclass(frozen=True)
class WxConfig:
    """Validated runtime configuration."""

    latitude: float
    longitude: float
    timezone: str
    provider_keys: Dict[str, str]


_REQUIRED_KEYS = ("WX_LAT", "WX_LON", "WX_TZ")


def load_config(env: Mapping[str, str] | None = None) -> WxConfig:
    """Validate environment variables and return a structured config.

    Args:
        env: A mapping of environment variables. Defaults to :data:`os.environ`.

    Returns:
        :class:`WxConfig` containing validated location and any optional
        provider keys.

    Raises:
        ConfigError: if any required value is missing or invalid.
    """

    environment = env if env is not None else os.environ
    latitude = _parse_coordinate("WX_LAT", environment, -90.0, 90.0)
    longitude = _parse_coordinate("WX_LON", environment, -180.0, 180.0)
    timezone = _parse_timezone(environment)
    provider_keys = _collect_provider_keys(environment)
    return WxConfig(latitude=latitude, longitude=longitude, timezone=timezone, provider_keys=provider_keys)


def _parse_coordinate(key: str, env: Mapping[str, str], min_value: float, max_value: float) -> float:
    raw_value = env.get(key)
    if raw_value is None or raw_value.strip() == "":
        raise ConfigError(f"Missing required configuration: {key}")

    try:
        value = float(raw_value)
    except ValueError as exc:  # pragma: no cover - defensive branch
        raise ConfigError(f"{key} must be a number") from exc

    if not (min_value <= value <= max_value):
        raise ConfigError(f"{key} must be between {min_value} and {max_value}")

    return value


def _parse_timezone(env: Mapping[str, str]) -> str:
    key = "WX_TZ"
    raw_value = env.get(key)
    if raw_value is None or raw_value.strip() == "":
        raise ConfigError("Missing required configuration: WX_TZ")

    try:
        ZoneInfo(raw_value)
    except ZoneInfoNotFoundError as exc:
        raise ConfigError(f"WX_TZ must be a valid IANA timezone, got: {raw_value}") from exc

    return raw_value


def _collect_provider_keys(env: Mapping[str, str]) -> Dict[str, str]:
    """Gather optional provider keys.

    Any environment variable beginning with ``WX_`` other than the required
    location keys will be returned. Empty values are ignored so callers can
    distinguish between absent and blank secrets.
    """

    optional_keys: Dict[str, str] = {}
    for key, value in env.items():
        if key in _REQUIRED_KEYS or not key.startswith("WX_"):
            continue
        if value:
            optional_keys[key] = value
    return optional_keys
