"""Shared helpers for provider payload mappers."""
from __future__ import annotations

from typing import Any, Optional


# ── Unit conversion constants ────────────────────────────────────────
INHG_TO_KPA = 3.386389
MPH_TO_KPH = 1.60934
INCH_TO_MM = 25.4
MPS_TO_KPH = 3.6


def _to_optional_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _to_optional_int(value: Any) -> Optional[int]:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
