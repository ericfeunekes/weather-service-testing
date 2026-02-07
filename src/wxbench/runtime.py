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
from wxbench.storage.parquet import (
    CompactionResult,
    ParquetDataPointWriter,
    ParquetReadError,
    datapoint_counts_by_run_at as parquet_counts_by_run_at,
    resolve_parquet_root,
)
from wxbench.storage.sqlite import (
    SqliteParquetIndexWriter,
    SqliteDataPointWriter,
    already_ran,
    datapoint_counts_by_run_at as sqlite_counts_by_run_at,
    ensure_schema,
    open_database,
    prune_data_points_for_runs,
    prune_raw_payloads_for_runs,
    prunable_run_ats,
    upsert_run_history,
    write_parquet_counts,
)
from wxbench.storage.datapoints import CompositeDataPointWriter

DEFAULT_DATA_ROOT = Path("data")
RUN_SKIP_STATUSES = ("success", "partial", "no_data")
PRUNE_VALIDATE_LIMIT = 24


def _run_id(run_at: datetime, started_at: datetime) -> str:
    return f"{run_at.strftime('%Y%m%dT%H%M%SZ')}_{started_at.strftime('%H%M%S')}"


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
    return already_ran(connection, run_at, skip_statuses=RUN_SKIP_STATUSES)


def _providers_requested(config) -> list[str]:
    providers = ["msc_geomet", "msc_rdps_prognos"]
    if config.provider_keys.get("WX_OPENWEATHER_API_KEY"):
        providers.append("openweather")
    if config.provider_keys.get("WX_TOMORROW_IO_API_KEY"):
        providers.append("tomorrow_io")
    if config.provider_keys.get("WX_ACCUWEATHER_API_KEY"):
        providers.append("accuweather")
    if (
        config.provider_keys.get("WX_ECOWITT_API_KEY")
        and config.provider_keys.get("WX_ECOWITT_APPLICATION_KEY")
        and config.provider_keys.get("WX_ECOWITT_DEVICE_MAC")
    ):
        providers.append("ecowitt")
    if config.provider_keys.get("WX_AMBIENT_API_KEY") and config.provider_keys.get("WX_AMBIENT_APPLICATION_KEY"):
        providers.append("ambient_weather")
    if (
        config.provider_keys.get("WX_WEATHERKIT_TEAM_ID")
        and config.provider_keys.get("WX_WEATHERKIT_SERVICE_ID")
        and config.provider_keys.get("WX_WEATHERKIT_KEY_ID")
        and config.provider_keys.get("WX_WEATHERKIT_KEY_PATH")
    ):
        providers.append("weatherkit")
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
    parquet_root: Path | None,
    parquet_exported_at: datetime | None,
    compaction_results: Iterable[CompactionResult],
) -> None:
    compaction_results = list(compaction_results)
    compaction_success = sum(1 for result in compaction_results if result.status == "success")
    compaction_skipped = sum(1 for result in compaction_results if result.status == "skipped")
    compaction_failed = sum(1 for result in compaction_results if result.status == "failed")
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
            "parquet": {
                "root": str(parquet_root) if parquet_root else None,
                "exported_at": parquet_exported_at.isoformat() if parquet_exported_at else None,
                "compaction": [
                    {
                        "partition": str(result.partition),
                        "day": result.day,
                        "status": result.status,
                        "error": result.error,
                        "input_files": result.input_files,
                        "output_file": str(result.output_file) if result.output_file else None,
                        "output_bytes": result.output_bytes,
                    }
                    for result in compaction_results
                ],
            },
        },
        "counts": {
            "raw_payloads": 0 if result is None else result.raw_payloads,
            "data_points": 0 if result is None else result.data_points,
        },
        "compaction": {
            "success": compaction_success,
            "skipped": compaction_skipped,
            "failed": compaction_failed,
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
        "parquet_compactions": compaction_success,
        "parquet_compactions_skipped": compaction_skipped,
        "parquet_compactions_failed": compaction_failed,
    }
    _write_json(run_dir / "metrics.json", metrics)


def _coerce_utc(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _validate_prune_window(
    *,
    connection: sqlite3.Connection,
    run_at_utc_values: list[str],
    logs_path: Path,
    parquet_root: Path,
) -> list[str]:
    if not run_at_utc_values:
        return []

    valid: list[str] = []
    for run_at_utc in run_at_utc_values:
        if not run_at_utc:
            continue
        run_at = _coerce_utc(run_at_utc)
        try:
            parquet_group = parquet_counts_by_run_at(parquet_root, run_at)
        except ParquetReadError as exc:
            _append_log(
                logs_path,
                {
                    "event": "prune_validation_failed",
                    "run_at_utc": run_at_utc,
                    "error": f"{exc.__class__.__name__}: {exc}",
                    "path": str(exc.path),
                },
            )
            continue
        sqlite_group = sqlite_counts_by_run_at(connection, run_at)
        if not parquet_group or parquet_group != sqlite_group:
            parquet_total = sum(parquet_group.values())
            sqlite_total = sum(sqlite_group.values())
            _append_log(
                logs_path,
                {
                    "event": "prune_validation_failed",
                    "run_at_utc": run_at_utc,
                    "parquet_groups": len(parquet_group),
                    "sqlite_groups": len(sqlite_group),
                    "parquet_total": parquet_total,
                    "sqlite_total": sqlite_total,
                },
            )
            continue
        valid.append(run_at_utc)
    return valid


def run_hourly(
    *,
    db_path: Path | None = None,
    now: datetime | None = None,
    msc_rdps_max_lead_hours: int = 24,
    data_root: Path | None = None,
) -> int:
    """Run a single hourly collection, writing a manifest + logs to disk."""

    started_at = datetime.now(timezone.utc)
    run_clock = now or datetime.now(timezone.utc)
    if run_clock.tzinfo is None:
        run_clock = run_clock.replace(tzinfo=timezone.utc)
    run_at = run_clock.replace(minute=0, second=0, microsecond=0)
    run_id = _run_id(run_at, started_at)

    try:
        config = load_config()
    except ConfigError as exc:
        sys.stderr.write(f"Config error: {exc}\n")
        return 2

    root = data_root or DEFAULT_DATA_ROOT
    run_dir = root / "runs" / run_id
    logs_path = run_dir / "logs.jsonl"
    lock_path = root / "wxbench.lock"
    resolved_db_path = db_path or (root / "wxbench.sqlite")
    parquet_root = resolve_parquet_root(root)
    parquet_writer: ParquetDataPointWriter | None = None

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

        def _writer_factory(connection: sqlite3.Connection):
            nonlocal parquet_writer
            index_writer = SqliteParquetIndexWriter(connection, parquet_root=parquet_root)
            parquet_writer = ParquetDataPointWriter(
                parquet_root,
                run_id=run_id,
                index_writer=index_writer,
            )
            return CompositeDataPointWriter(
                parquet_writer=parquet_writer,
                sqlite_writer=SqliteDataPointWriter(connection),
            )

        result = collect_all(
            config,
            db_path=resolved_db_path,
            clock=lambda: run_at,
            msc_rdps_max_lead_hours=msc_rdps_max_lead_hours,
            data_point_writer_factory=_writer_factory,
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
        wrote_any = parquet_writer is not None and parquet_writer.wrote_any
        parquet_exported_at = finished_at if wrote_any and status not in {"error", "skipped"} else None
        compaction_results: list[CompactionResult] = []
        # Compaction is handled by the separate compact_sweep job.
        try:
            maintenance_connection = open_database(resolved_db_path)
            ensure_schema(maintenance_connection)
            if status != "skipped":
                upsert_run_history(
                    maintenance_connection,
                    run_at=run_at,
                    run_id=run_id,
                    status=status,
                    parquet_exported_at=parquet_exported_at,
                    parquet_root=parquet_root,
                    raw_payloads=0 if result is None else result.raw_payloads,
                    data_points=0 if result is None else result.data_points,
                )
                if parquet_writer is not None and parquet_writer.index_errors:
                    for error in parquet_writer.index_errors:
                        _append_log(
                            logs_path,
                            {
                                "event": "parquet_index_error",
                                "error": error,
                            },
                        )
                if parquet_exported_at is not None and parquet_writer is not None:
                    write_parquet_counts(
                        maintenance_connection,
                        run_at=run_at,
                        counts=parquet_writer.counts(),
                    )
            cutoff_points = finished_at - timedelta(hours=24)
            cutoff_raw = finished_at - timedelta(days=7)
            candidates_points = prunable_run_ats(
                maintenance_connection, cutoff_run_at_utc=cutoff_points, limit=PRUNE_VALIDATE_LIMIT
            )
            candidates_raw = prunable_run_ats(
                maintenance_connection, cutoff_run_at_utc=cutoff_raw, limit=PRUNE_VALIDATE_LIMIT
            )
            validated_points = _validate_prune_window(
                connection=maintenance_connection,
                run_at_utc_values=candidates_points,
                logs_path=logs_path,
                parquet_root=parquet_root,
            )
            pruned_points = 0
            if validated_points:
                pruned_points = prune_data_points_for_runs(maintenance_connection, validated_points)
            validated_raw = [value for value in candidates_raw if value in validated_points]
            pruned_raw = 0
            if validated_raw:
                pruned_raw = prune_raw_payloads_for_runs(maintenance_connection, validated_raw)
            if validated_points or validated_raw:
                _append_log(
                    logs_path,
                    {
                        "event": "prune_summary",
                        "validated_count": len(validated_points),
                        "pruned_points": pruned_points,
                        "pruned_raw": pruned_raw,
                    },
                )
            maintenance_connection.commit()
            maintenance_connection.close()
        except Exception as maint_exc:  # noqa: BLE001
            _append_log(
                logs_path,
                {
                    "event": "maintenance_error",
                    "error": f"{maint_exc.__class__.__name__}: {maint_exc}",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
            )
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
            parquet_root=parquet_root,
            parquet_exported_at=parquet_exported_at,
            compaction_results=compaction_results,
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
