"""Append-only JSONL storage for normalized weather records."""
from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Callable, Iterable, Mapping, Any

from wxbench.domain.models import ForecastPeriod, Observation

NormalizedRecord = Observation | ForecastPeriod

DEFAULT_STORAGE_ROOT = Path("data")


Clock = Callable[[], datetime]


def _default_clock() -> datetime:
    return datetime.now(timezone.utc)


def _serialize(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if is_dataclass(value):
        return {key: _serialize(val) for key, val in asdict(value).items()}
    if isinstance(value, Mapping):
        return {key: _serialize(val) for key, val in value.items()}
    if isinstance(value, list):
        return [_serialize(item) for item in value]
    return value


def _target_path(provider: str, root: Path, now: datetime) -> Path:
    day = now.date().isoformat()
    return root / day / f"{provider}.jsonl"


def append_records(
    provider: str,
    records: Iterable[NormalizedRecord],
    *,
    storage_root: Path | None = None,
    clock: Clock | None = None,
) -> Path:
    """Append normalized records to a provider's daily JSONL file.

    Args:
        provider: Provider identifier used to name the output file.
        records: Iterable of normalized domain records to persist.
        storage_root: Base directory for JSONL output. Defaults to ``data``.
        clock: Callable returning the current :class:`datetime`. Injected for testing.

    Returns:
        Path to the JSONL file that was written.
    """

    now = (clock or _default_clock)()
    destination = _target_path(provider, storage_root or DEFAULT_STORAGE_ROOT, now)
    destination.parent.mkdir(parents=True, exist_ok=True)
    stored_at = now.isoformat()

    with destination.open("a", encoding="utf-8") as handle:
        for record in records:
            payload = {
                "provider": provider,
                "stored_at": stored_at,
                "kind": "observation" if isinstance(record, Observation) else "forecast_period",
                "data": _serialize(record),
            }
            handle.write(json.dumps(payload, sort_keys=True))
            handle.write("\n")

    return destination
