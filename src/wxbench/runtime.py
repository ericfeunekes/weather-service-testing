"""Runtime helpers for scheduled collection runs."""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable

try:
    import fcntl  # type: ignore[attr-defined]
except ImportError:  # pragma: no cover - platform specific
    fcntl = None

from wxbench.config import ConfigError, load_config
from wxbench.pipeline import CollectionResult, collect_all
from wxbench.storage.sqlite import ensure_schema, open_database

DEFAULT_DATA_ROOT = Path("data")


def _run_id(run_at: datetime, started_at: datetime) -> str:
    return f"{run_at.strftime('%Y%m%dT%H%M%SZ')}_{started_at.strftime('%H%M%S')}"


def _hour_window(run_at: datetime) -> tuple[datetime, datetime]:
    start = run_at.replace(minute=0, second=0, microsecond=0)
    end = start + timedelta(hours=1)
    return start, end


def _acquire_lock(path: Path) -> object | None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = path.open("w")
    if fcntl is None:
        return handle
    try:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        handle.close()
        return None
    return handle


def _already_ran(connection: sqlite3.Connection, run_at: datetime) -> bool:
    start, end = _hour_window(run_at)
    row = connection.execute(
        "SELECT 1 FROM data_points WHERE run_at_utc >= ? AND run_at_utc < ? LIMIT 1",
        (start.isoformat(), end.isoformat()),
    ).fetchone()
    return row is not None


def _providers_requested(config) -> list[str]:
    providers = ["msc_geomet", "msc_rdps_prognos"]
    if config.provider_keys.get("WX_OPENWEATHER_API_KEY"):
        providers.append("openweather")
    if config.provider_keys.get("WX_TOMORROW_IO_API_KEY"):
        providers.append("tomorrow_io")
    if config.provider_keys.get("WX_ACCUWEATHER_API_KEY"):
        providers.append("accuweather")
    if config.provider_keys.get("WX_AMBIENT_API_KEY") and config.provider_keys.get("WX_AMBIENT_APPLICATION_KEY"):
        providers.append("ambient_weather")
    return providers


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _append_log(path: Path, event: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, sort_keys=True))
        handle.write("\n")


def _emit_manifest(
    *,
    run_dir: Path,
    run_at: datetime,
    config,
    db_path: Path,
    result: CollectionResult | None,
    errors: Iterable[str],
    status: str,
    started_at: datetime,
    finished_at: datetime,
) -> None:
    manifest = {
        "run_id": _run_id(run_at, started_at),
        "run_at_utc": run_at.isoformat(),
        "hour_bucket": run_at.strftime("%Y%m%dT%H%M%SZ"),
        "status": status,
        "parameters": {
            "latitude": config.latitude,
            "longitude": config.longitude,
            "timezone": config.timezone,
            "providers": _providers_requested(config),
        },
        "outputs": {
            "sqlite": str(db_path),
        },
        "counts": {
            "raw_payloads": 0 if result is None else result.raw_payloads,
            "data_points": 0 if result is None else result.data_points,
        },
        "errors": list(errors),
        "started_at": started_at.isoformat(),
        "finished_at": finished_at.isoformat(),
    }
    _write_json(run_dir / "manifest.json", manifest)

    metrics = {
        "run_id": manifest["run_id"],
        "duration_seconds": (finished_at - started_at).total_seconds(),
        "raw_payloads": manifest["counts"]["raw_payloads"],
        "data_points": manifest["counts"]["data_points"],
        "errors": len(manifest["errors"]),
    }
    _write_json(run_dir / "metrics.json", metrics)


def run_hourly(
    *,
    db_path: Path | None = None,
    now: datetime | None = None,
    msc_rdps_max_lead_hours: int = 24,
    data_root: Path | None = None,
) -> int:
    """Run a single hourly collection, writing a manifest + logs to disk."""

    started_at = datetime.now(timezone.utc)

    try:
        config = load_config()
    except ConfigError as exc:
        sys.stderr.write(f"Config error: {exc}\n")
        return 2

    run_clock = now or datetime.now(timezone.utc)
    if run_clock.tzinfo is None:
        run_clock = run_clock.replace(tzinfo=timezone.utc)
    run_at = run_clock.replace(minute=0, second=0, microsecond=0)

    root = data_root or DEFAULT_DATA_ROOT
    run_dir = root / "runs" / _run_id(run_at, started_at)
    logs_path = run_dir / "logs.jsonl"
    lock_path = root / "wxbench.lock"

    lock = _acquire_lock(lock_path)
    if lock is None:
        _append_log(
            logs_path,
            {
                "event": "skip",
                "reason": "lock_unavailable",
                "run_at_utc": run_at.isoformat(),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )
        return 0

    errors: list[str] = []
    result: CollectionResult | None = None
    status = "success"
    try:
        _append_log(
            logs_path,
            {
                "event": "start",
                "run_at_utc": run_at.isoformat(),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )

        resolved_db_path = db_path or (root / "wxbench.sqlite")
        connection = open_database(resolved_db_path)
        ensure_schema(connection)
        if _already_ran(connection, run_at):
            status = "skipped"
            _append_log(
                logs_path,
                {
                    "event": "skip",
                    "reason": "already_ran",
                    "run_at_utc": run_at.isoformat(),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
            )
            connection.close()
            return 0
        connection.close()

        def _log_event(event: dict[str, object]) -> None:
            payload = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "run_at_utc": run_at.isoformat(),
                **event,
            }
            _append_log(logs_path, payload)

        result = collect_all(
            config,
            db_path=resolved_db_path,
            clock=lambda: run_at,
            msc_rdps_max_lead_hours=msc_rdps_max_lead_hours,
            event_logger=_log_event,
        )
        if result.errors:
            errors.extend(result.errors)
            status = "partial"
        if result.raw_payloads == 0:
            status = "no_data"
            errors.append("no_payloads_collected")
            return_code = 1
        else:
            return_code = 0
        return return_code
    except Exception as exc:  # noqa: BLE001
        status = "error"
        errors.append(f"{exc.__class__.__name__}: {exc}")
        return 2
    finally:
        finished_at = datetime.now(timezone.utc)
        _emit_manifest(
            run_dir=run_dir,
            run_at=run_at,
            config=config,
            db_path=resolved_db_path,
            result=result,
            errors=errors,
            status=status,
            started_at=started_at,
            finished_at=finished_at,
        )
        _append_log(
            logs_path,
            {
                "event": "finish",
                "run_at_utc": run_at.isoformat(),
                "status": status,
                "timestamp": finished_at.isoformat(),
            },
        )
        try:
            lock.close()
        except Exception:  # pragma: no cover - defensive
            pass


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run hourly weather collection.")
    parser.add_argument(
        "--data-root",
        type=Path,
        default=None,
        help="Base directory for run artifacts and default SQLite path.",
    )
    parser.add_argument(
        "--db-path",
        type=Path,
        default=None,
        help="Path to the SQLite database (defaults to data/wxbench.sqlite)",
    )
    parser.add_argument(
        "--msc-rdps-max-lead-hours",
        type=int,
        default=24,
        help="Maximum RDPS PROGNOS lead hours to fetch (default: 24)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv or sys.argv[1:])
    return run_hourly(
        db_path=args.db_path,
        msc_rdps_max_lead_hours=args.msc_rdps_max_lead_hours,
        data_root=args.data_root,
    )


if __name__ == "__main__":
    raise SystemExit(main())
