"""Backfill SQLite data_points into partitioned Parquet."""
from __future__ import annotations

import argparse
import sys
from datetime import date, datetime, timedelta, timezone

try:
    import fcntl  # type: ignore[attr-defined]
except ImportError:  # pragma: no cover - platform specific
    fcntl = None
from pathlib import Path

from wxbench.domain.models import DataPoint
from wxbench.storage.parquet import ParquetDataPointWriter, resolve_parquet_root
from wxbench.storage.sqlite import (
    SqliteParquetIndexWriter,
    ensure_schema,
    open_database,
    upsert_run_history,
    write_parquet_counts,
)


def _parse_datetime(value: str | None) -> datetime | None:
    if value is None:
        return None
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _parse_date(value: str | None) -> date | None:
    if value is None:
        return None
    return date.fromisoformat(value)


def _row_to_datapoint(row: tuple) -> DataPoint:
    (
        provider,
        product_kind,
        metric_type,
        value_num,
        value_text,
        unit,
        value_raw,
        unit_raw,
        observed_at_utc,
        valid_start_utc,
        valid_end_utc,
        issued_at_utc,
        run_at_utc,
        local_day,
        lead_unit,
        lead_offset,
        lead_label,
        lead_day_index,
        latitude,
        longitude,
        station,
        source_field,
        quality_flag,
    ) = row
    return DataPoint(
        provider=provider,
        product_kind=product_kind,
        metric_type=metric_type,
        value_num=value_num,
        value_text=value_text,
        unit=unit,
        value_raw=value_raw,
        unit_raw=unit_raw,
        observed_at=_parse_datetime(observed_at_utc),
        valid_start=_parse_datetime(valid_start_utc),
        valid_end=_parse_datetime(valid_end_utc),
        issued_at=_parse_datetime(issued_at_utc),
        run_at=_parse_datetime(run_at_utc) or datetime.now(timezone.utc),
        local_day=_parse_date(local_day),
        lead_unit=lead_unit,
        lead_offset=lead_offset,
        lead_label=lead_label,
        lead_day_index=lead_day_index,
        latitude=latitude,
        longitude=longitude,
        station=station,
        source_field=source_field,
        quality_flag=quality_flag,
    )


def run_backfill(
    *,
    db_path: Path | None,
    data_root: Path | None,
    acquire_lock: bool = True,
) -> int:
    resolved_root = data_root or (db_path.parent if db_path else Path("data"))
    lock = None
    if acquire_lock:
        lock_path = resolved_root / "wxbench.lock"
        lock = _acquire_lock(lock_path)
        if lock is None:
            sys.stderr.write("Backfill skipped: lock unavailable\n")
            return 0

    connection = open_database(db_path)
    ensure_schema(connection)
    parquet_root = resolve_parquet_root(resolved_root)

    run_at_rows = connection.execute(
        "SELECT DISTINCT run_at_utc FROM data_points ORDER BY run_at_utc"
    ).fetchall()

    for (run_at_str,) in run_at_rows:
        if not run_at_str:
            continue
        run_at = _parse_datetime(run_at_str) or datetime.now(timezone.utc)
        run_stamp = run_at.strftime("%Y%m%dT%H%M%SZ")
        run_id = f"backfill-{run_stamp}"
        _delete_run_stamp_files(parquet_root, run_stamp)
        index_writer = SqliteParquetIndexWriter(connection, parquet_root=parquet_root)
        writer = ParquetDataPointWriter(parquet_root, run_id=run_id, index_writer=index_writer)

        cursor = connection.execute(
            """
            SELECT
                provider,
                product_kind,
                metric_type,
                value_num,
                value_text,
                unit,
                value_raw,
                unit_raw,
                observed_at_utc,
                valid_start_utc,
                valid_end_utc,
                issued_at_utc,
                run_at_utc,
                local_day,
                lead_unit,
                lead_offset,
                lead_label,
                lead_day_index,
                latitude,
                longitude,
                station,
                source_field,
                quality_flag,
                raw_id
            FROM data_points
            WHERE run_at_utc = ?
            ORDER BY raw_id, id
            """,
            (run_at_str,),
        )

        total_points = 0
        current_raw_id = None
        buffer: list[DataPoint] = []
        for row in cursor:
            *point_fields, raw_id = row
            point = _row_to_datapoint(tuple(point_fields))
            if current_raw_id is None:
                current_raw_id = raw_id
            if raw_id != current_raw_id:
                total_points += writer.write(current_raw_id, buffer, run_at=run_at)
                buffer = []
                current_raw_id = raw_id
            buffer.append(point)

        if current_raw_id is not None and buffer:
            total_points += writer.write(current_raw_id, buffer, run_at=run_at)

        upsert_run_history(
            connection,
            run_at=run_at,
            run_id=run_id,
            status="backfill",
            parquet_exported_at=datetime.now(timezone.utc),
            parquet_root=parquet_root,
            raw_payloads=None,
            data_points=total_points,
        )
        write_parquet_counts(connection, run_at=run_at, counts=writer.counts())
        connection.commit()

    connection.close()
    if lock is not None:
        try:
            lock.close()
        except Exception:  # pragma: no cover - defensive
            pass
    return 0


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


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backfill SQLite data_points to Parquet.")
    parser.add_argument(
        "--db-path",
        type=Path,
        default=None,
        help="Path to the SQLite database (defaults to data/wxbench.sqlite).",
    )
    parser.add_argument(
        "--data-root",
        type=Path,
        default=None,
        help="Root directory for Parquet output (defaults to data/).",
    )
    parser.add_argument(
        "--run-at",
        type=str,
        default=None,
        help="Optional run_at_utc ISO timestamp to backfill (e.g. 2025-12-29T13:00:00+00:00).",
    )
    parser.add_argument(
        "--run-day",
        type=str,
        default=None,
        help="Optional UTC day (YYYY-MM-DD) to backfill.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv or sys.argv[1:])
    if args.run_at and args.run_day:
        sys.stderr.write("Provide only one of --run-at or --run-day\n")
        return 2
    if args.run_at:
        return run_backfill_single(
            db_path=args.db_path,
            data_root=args.data_root,
            run_at_str=args.run_at,
        )
    if args.run_day:
        return run_backfill_day(
            db_path=args.db_path,
            data_root=args.data_root,
            run_day=args.run_day,
        )
    return run_backfill(db_path=args.db_path, data_root=args.data_root)


def run_backfill_single(*, db_path: Path | None, data_root: Path | None, run_at_str: str) -> int:
    run_at = _parse_datetime(run_at_str)
    if run_at is None:
        sys.stderr.write("Invalid --run-at value\n")
        return 2

    resolved_root = data_root or (db_path.parent if db_path else Path("data"))
    lock_path = resolved_root / "wxbench.lock"
    lock = _acquire_lock(lock_path)
    if lock is None:
        sys.stderr.write("Backfill skipped: lock unavailable\n")
        return 0

    connection = open_database(db_path)
    ensure_schema(connection)
    parquet_root = resolve_parquet_root(resolved_root)
    run_stamp = run_at.strftime("%Y%m%dT%H%M%SZ")
    run_id = f"backfill-{run_stamp}"
    _delete_run_stamp_files(parquet_root, run_stamp)
    index_writer = SqliteParquetIndexWriter(connection, parquet_root=parquet_root)
    writer = ParquetDataPointWriter(parquet_root, run_id=run_id, index_writer=index_writer)

    cursor = connection.execute(
        """
        SELECT
            provider,
            product_kind,
            metric_type,
            value_num,
            value_text,
            unit,
            value_raw,
            unit_raw,
            observed_at_utc,
            valid_start_utc,
            valid_end_utc,
            issued_at_utc,
            run_at_utc,
            local_day,
            lead_unit,
            lead_offset,
            lead_label,
            lead_day_index,
            latitude,
            longitude,
            station,
            source_field,
            quality_flag,
            raw_id
        FROM data_points
        WHERE run_at_utc = ?
        ORDER BY raw_id, id
        """,
        (run_at_str,),
    )

    total_points = 0
    current_raw_id = None
    buffer: list[DataPoint] = []
    for row in cursor:
        *point_fields, raw_id = row
        point = _row_to_datapoint(tuple(point_fields))
        if current_raw_id is None:
            current_raw_id = raw_id
        if raw_id != current_raw_id:
            total_points += writer.write(current_raw_id, buffer, run_at=run_at)
            buffer = []
            current_raw_id = raw_id
        buffer.append(point)

    if current_raw_id is not None and buffer:
        total_points += writer.write(current_raw_id, buffer, run_at=run_at)

    upsert_run_history(
        connection,
        run_at=run_at,
        run_id=run_id,
        status="backfill",
        parquet_exported_at=datetime.now(timezone.utc),
        parquet_root=parquet_root,
        raw_payloads=None,
        data_points=total_points,
    )
    write_parquet_counts(connection, run_at=run_at, counts=writer.counts())
    connection.commit()
    connection.close()
    return 0


def run_backfill_day(*, db_path: Path | None, data_root: Path | None, run_day: str) -> int:
    try:
        day = date.fromisoformat(run_day)
    except ValueError:
        sys.stderr.write("Invalid --run-day value\n")
        return 2

    resolved_root = data_root or (db_path.parent if db_path else Path("data"))
    lock_path = resolved_root / "wxbench.lock"
    lock = _acquire_lock(lock_path)
    if lock is None:
        sys.stderr.write("Backfill skipped: lock unavailable\n")
        return 0

    connection = open_database(db_path)
    ensure_schema(connection)
    parquet_root = resolve_parquet_root(resolved_root)

    day_start = datetime(day.year, day.month, day.day, tzinfo=timezone.utc)
    day_end = day_start + timedelta(days=1)
    run_at_rows = connection.execute(
        """
        SELECT DISTINCT run_at_utc
        FROM data_points
        WHERE run_at_utc >= ? AND run_at_utc < ?
        ORDER BY run_at_utc
        """,
        (day_start.isoformat(), day_end.isoformat()),
    ).fetchall()

    for (run_at_str,) in run_at_rows:
        if not run_at_str:
            continue
        run_at = _parse_datetime(run_at_str) or datetime.now(timezone.utc)
        run_stamp = run_at.strftime("%Y%m%dT%H%M%SZ")
        run_id = f"backfill-{run_stamp}"
        _delete_run_stamp_files(parquet_root, run_stamp)
        index_writer = SqliteParquetIndexWriter(connection, parquet_root=parquet_root)
        writer = ParquetDataPointWriter(parquet_root, run_id=run_id, index_writer=index_writer)

        cursor = connection.execute(
            """
            SELECT
                provider,
                product_kind,
                metric_type,
                value_num,
                value_text,
                unit,
                value_raw,
                unit_raw,
                observed_at_utc,
                valid_start_utc,
                valid_end_utc,
                issued_at_utc,
                run_at_utc,
                local_day,
                lead_unit,
                lead_offset,
                lead_label,
                lead_day_index,
                latitude,
                longitude,
                station,
                source_field,
                quality_flag,
                raw_id
            FROM data_points
            WHERE run_at_utc = ?
            ORDER BY raw_id, id
            """,
            (run_at_str,),
        )

        total_points = 0
        current_raw_id = None
        buffer: list[DataPoint] = []
        for row in cursor:
            *point_fields, raw_id = row
            point = _row_to_datapoint(tuple(point_fields))
            if current_raw_id is None:
                current_raw_id = raw_id
            if raw_id != current_raw_id:
                total_points += writer.write(current_raw_id, buffer, run_at=run_at)
                buffer = []
                current_raw_id = raw_id
            buffer.append(point)

        if current_raw_id is not None and buffer:
            total_points += writer.write(current_raw_id, buffer, run_at=run_at)

        upsert_run_history(
            connection,
            run_at=run_at,
            run_id=run_id,
            status="backfill",
            parquet_exported_at=datetime.now(timezone.utc),
            parquet_root=parquet_root,
            raw_payloads=None,
            data_points=total_points,
        )
        write_parquet_counts(connection, run_at=run_at, counts=writer.counts())
        connection.commit()

    connection.close()
    return 0


def _delete_run_stamp_files(parquet_root: Path, run_stamp: str) -> None:
    pattern = f"*{run_stamp}*"
    for path in parquet_root.rglob(pattern):
        if path.is_file():
            path.unlink(missing_ok=True)


if __name__ == "__main__":
    raise SystemExit(main())
