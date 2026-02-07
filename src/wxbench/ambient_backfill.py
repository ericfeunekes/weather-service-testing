"""Backfill Ambient Weather historical observations (5-minute cadence)."""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import httpx

from wxbench.config import ConfigError, load_config
from wxbench.domain.datapoints import observation_to_datapoints
from wxbench.providers import (
    fetch_ambient_weather_history,
    fetch_ambient_weather_observation,
)
from wxbench.providers.capture import CapturedPayload
from wxbench.storage.sqlite import (
    RawPayload,
    SqliteDataPointWriter,
    ensure_schema,
    insert_raw_payload,
    open_database,
)
from wxbench.storage.parquet import ParquetDataPointWriter, resolve_parquet_root
from wxbench.storage.datapoints import CompositeDataPointWriter


DEFAULT_LOOKBACK_HOURS = 2


def _default_now() -> datetime:
    return datetime.now(timezone.utc)


def _coerce_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _existing_observed_at(
    connection,
    *,
    provider: str,
    start: datetime,
    end: datetime,
) -> set[str]:
    rows = connection.execute(
        """
        SELECT DISTINCT observed_at_utc
        FROM data_points
        WHERE provider = ?
          AND product_kind = 'observation'
          AND observed_at_utc IS NOT NULL
          AND observed_at_utc >= ?
          AND observed_at_utc <= ?
        """,
        (provider, start.isoformat(), end.isoformat()),
    ).fetchall()
    return {row[0] for row in rows if row[0]}


def _to_raw_payload(captured: CapturedPayload, *, run_at: datetime) -> RawPayload:
    return RawPayload(
        provider=captured.provider,
        endpoint=captured.endpoint,
        run_at=run_at,
        request_url=captured.request_url,
        request_params=captured.request_params,
        request_headers=captured.request_headers,
        response_status=captured.response_status,
        response_headers=captured.response_headers,
        payload_json=captured.payload_text,
    )


def run_ambient_history_backfill(
    *,
    db_path: Optional[Path] = None,
    lookback_hours: int = DEFAULT_LOOKBACK_HOURS,
    device_mac: Optional[str] = None,
    now: Optional[datetime] = None,
    dry_run: bool = False,
) -> int:
    """Backfill Ambient history observations for a lookback window."""

    try:
        config = load_config()
    except ConfigError as exc:
        sys.stderr.write(f"Config error: {exc}\n")
        return 2

    api_key = config.provider_keys.get("WX_AMBIENT_API_KEY")
    application_key = config.provider_keys.get("WX_AMBIENT_APPLICATION_KEY")
    resolved_mac = device_mac or config.provider_keys.get("WX_AMBIENT_DEVICE_MAC")

    if not api_key or not application_key:
        sys.stderr.write("Missing WX_AMBIENT_API_KEY or WX_AMBIENT_APPLICATION_KEY\n")
        return 2
    if not resolved_mac:
        sys.stderr.write("Missing WX_AMBIENT_DEVICE_MAC (required for history backfill)\n")
        return 2

    run_at = _coerce_utc(now or _default_now())
    window_end = run_at
    window_start = run_at - timedelta(hours=lookback_hours)

    connection = open_database(db_path)
    ensure_schema(connection)
    data_root = db_path.parent if db_path else Path("data")
    parquet_root = resolve_parquet_root(data_root)
    run_id = f"ambient-backfill-{run_at.strftime('%Y%m%dT%H%M%SZ')}"
    parquet_writer = ParquetDataPointWriter(parquet_root, run_id=run_id)
    data_point_writer = CompositeDataPointWriter(
        parquet_writer=parquet_writer,
        sqlite_writer=SqliteDataPointWriter(connection),
    )
    existing = _existing_observed_at(
        connection,
        provider="ambient_weather",
        start=window_start,
        end=window_end,
    )

    holder: dict[str, int] = {}

    def _capture(captured: CapturedPayload) -> None:
        raw_id = insert_raw_payload(connection, _to_raw_payload(captured, run_at=run_at))
        holder["raw_id"] = raw_id

    with httpx.Client() as session:
        current = fetch_ambient_weather_observation(
            api_key=api_key,
            application_key=application_key,
            device_mac=resolved_mac,
            client=session,
        )
        observations = fetch_ambient_weather_history(
            api_key=api_key,
            application_key=application_key,
            device_mac=resolved_mac,
            location=current.location,
            station=current.station,
            end_at=window_end,
            client=session,
            capture=None if dry_run else _capture,
        )

    observations = [
        obs
        for obs in observations
        if window_start <= obs.observed_at <= window_end
        and obs.observed_at.isoformat() not in existing
    ]

    if dry_run:
        sys.stdout.write(
            f"Ambient history backfill dry-run: {len(observations)} missing observations in last {lookback_hours}h\n"
        )
        connection.close()
        return 0

    raw_id = holder.get("raw_id")
    if not raw_id:
        sys.stderr.write("No raw payload captured for Ambient history\n")
        connection.close()
        return 1

    points = []
    for observation in observations:
        points.extend(observation_to_datapoints(observation, run_at=run_at, tz_name=config.timezone))

    data_point_writer.write(raw_id, points, run_at=run_at)
    connection.commit()
    connection.close()

    sys.stdout.write(
        f"Ambient history backfill stored {len(observations)} observations ({len(points)} data points)\n"
    )
    return 0


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backfill Ambient Weather historical observations.")
    parser.add_argument(
        "--db-path",
        type=Path,
        default=None,
        help="Path to the SQLite database (defaults to data/wxbench.sqlite).",
    )
    parser.add_argument(
        "--lookback-hours",
        type=int,
        default=DEFAULT_LOOKBACK_HOURS,
        help="Hours to look back for history (default: 2).",
    )
    parser.add_argument(
        "--device-mac",
        type=str,
        default=None,
        help="Override device MAC address (defaults to WX_AMBIENT_DEVICE_MAC).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report missing observations without writing data.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv or sys.argv[1:])
    return run_ambient_history_backfill(
        db_path=args.db_path,
        lookback_hours=args.lookback_hours,
        device_mac=args.device_mac,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    raise SystemExit(main())
