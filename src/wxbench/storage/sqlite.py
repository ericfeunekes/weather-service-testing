"""SQLite storage for raw payloads and normalized data points."""
from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import date, datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Iterable, Mapping, Optional, Sequence

from wxbench.domain.models import DataPoint
from wxbench.storage.datapoints import PartitionKey
from wxbench.storage.parquet import INDEX_ALL, ParquetFileRecord


DEFAULT_DB_PATH = Path("data") / "wxbench.sqlite"


@dataclass(frozen=True)
class RawPayload:
    """Captured HTTP exchange payload."""

    provider: str
    endpoint: str
    run_at: datetime
    request_url: str
    request_params: Optional[Mapping[str, str]]
    request_headers: Optional[Mapping[str, str]]
    response_status: int
    response_headers: Optional[Mapping[str, str]]
    payload_json: str


def open_database(path: Path | None = None, *, timeout_seconds: float = 30.0) -> sqlite3.Connection:
    """Open a SQLite database connection (creates file if missing)."""

    target = path or DEFAULT_DB_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(target, timeout=timeout_seconds)
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("PRAGMA foreign_keys=ON")
    connection.execute("PRAGMA busy_timeout=5000")
    return connection


def ensure_schema(connection: sqlite3.Connection) -> None:
    """Create required tables if they do not exist."""

    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS raw_payloads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            provider TEXT NOT NULL,
            endpoint TEXT NOT NULL,
            run_at_utc TEXT NOT NULL,
            request_url TEXT NOT NULL,
            request_params_json TEXT,
            request_headers_json TEXT,
            response_status INTEGER NOT NULL,
            response_headers_json TEXT,
            payload_json TEXT NOT NULL,
            payload_sha256 TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS data_points (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            raw_id INTEGER NOT NULL,
            provider TEXT NOT NULL,
            product_kind TEXT NOT NULL,
            metric_type TEXT NOT NULL,
            value_num REAL,
            value_text TEXT,
            unit TEXT,
            value_raw TEXT,
            unit_raw TEXT,
            observed_at_utc TEXT,
            valid_start_utc TEXT,
            valid_end_utc TEXT,
            issued_at_utc TEXT,
            run_at_utc TEXT NOT NULL,
            local_day TEXT,
            lead_unit TEXT,
            lead_offset INTEGER,
            lead_label TEXT,
            lead_day_index INTEGER,
            latitude REAL NOT NULL,
            longitude REAL NOT NULL,
            station TEXT,
            source_field TEXT,
            quality_flag TEXT,
            FOREIGN KEY(raw_id) REFERENCES raw_payloads(id)
        );

        CREATE INDEX IF NOT EXISTS idx_raw_payloads_provider_run ON raw_payloads(provider, run_at_utc);
        CREATE INDEX IF NOT EXISTS idx_data_points_provider_kind ON data_points(provider, product_kind);
        CREATE INDEX IF NOT EXISTS idx_data_points_metric ON data_points(metric_type);
        CREATE INDEX IF NOT EXISTS idx_data_points_time ON data_points(run_at_utc, valid_start_utc, observed_at_utc);

        CREATE TABLE IF NOT EXISTS run_history (
            run_at_utc TEXT PRIMARY KEY,
            run_id TEXT NOT NULL,
            status TEXT NOT NULL,
            parquet_exported_at TEXT,
            parquet_root TEXT,
            raw_payloads INTEGER,
            data_points INTEGER,
            updated_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_run_history_status ON run_history(status);

        CREATE TABLE IF NOT EXISTS parquet_counts (
            run_at_utc TEXT NOT NULL,
            provider TEXT NOT NULL,
            product_kind TEXT NOT NULL,
            metric_type TEXT NOT NULL,
            count INTEGER NOT NULL,
            updated_at TEXT NOT NULL,
            PRIMARY KEY (run_at_utc, provider, product_kind, metric_type)
        );

        CREATE TABLE IF NOT EXISTS parquet_file_index (
            path TEXT PRIMARY KEY,
            provider TEXT NOT NULL,
            product_kind TEXT NOT NULL,
            metric_type TEXT NOT NULL,
            day TEXT NOT NULL,
            size_bytes INTEGER NOT NULL,
            mtime INTEGER NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_parquet_file_index_day ON parquet_file_index(day);
        CREATE INDEX IF NOT EXISTS idx_parquet_file_index_provider ON parquet_file_index(provider);

        CREATE TABLE IF NOT EXISTS parquet_sync (
            target TEXT NOT NULL,
            path TEXT NOT NULL,
            size_bytes INTEGER NOT NULL,
            mtime INTEGER NOT NULL,
            synced_at TEXT NOT NULL,
            status TEXT NOT NULL,
            error TEXT,
            PRIMARY KEY (target, path, size_bytes, mtime)
        );

        CREATE INDEX IF NOT EXISTS idx_parquet_sync_target_status ON parquet_sync(target, status);
        """
    )
    _ensure_column(connection, "data_points", "lead_day_index", "INTEGER")
    _ensure_column(connection, "run_history", "data_points_pruned_at", "TEXT")
    _ensure_column(connection, "run_history", "raw_payloads_pruned_at", "TEXT")
    # Backfill runs were written directly to parquet and never had SQLite data
    # points or raw payloads — mark them as already pruned so they don't block
    # the pruning queue.
    connection.execute(
        """
        UPDATE run_history
        SET data_points_pruned_at = updated_at,
            raw_payloads_pruned_at = updated_at
        WHERE status = 'backfill'
          AND data_points_pruned_at IS NULL
        """
    )


class SqliteDataPointWriter:
    """Write data points to SQLite (overlap window)."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def write(self, raw_id: int, points: Iterable[DataPoint], *, run_at: datetime) -> int:
        buffered = list(points)
        insert_data_points(self._connection, raw_id, buffered)
        return len(buffered)

    def touched_partitions(self) -> tuple[PartitionKey, ...]:
        return ()


@dataclass(frozen=True)
class ParquetIndexRow:
    path: str
    provider: str
    product_kind: str
    metric_type: str
    day: str
    size_bytes: int
    mtime: int


class SqliteParquetIndexWriter:
    """Record parquet file metadata in SQLite."""

    def __init__(self, connection: sqlite3.Connection, *, parquet_root: Path) -> None:
        self._connection = connection
        self._parquet_root = parquet_root

    def record_files(self, files: Iterable[ParquetFileRecord]) -> None:
        now = _serialize_datetime(datetime.now(timezone.utc))
        rows = []
        for record in files:
            try:
                rel_path = str(record.path.relative_to(self._parquet_root))
            except ValueError:
                rel_path = str(record.path)
            rows.append(
                (
                    rel_path,
                    record.provider,
                    record.product_kind,
                    record.metric_type,
                    record.day,
                    record.size_bytes,
                    record.mtime,
                    now,
                )
            )
        if not rows:
            return
        self._connection.executemany(
            """
            INSERT INTO parquet_file_index (
                path,
                provider,
                product_kind,
                metric_type,
                day,
                size_bytes,
                mtime,
                updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(path) DO UPDATE SET
                provider = excluded.provider,
                product_kind = excluded.product_kind,
                metric_type = excluded.metric_type,
                day = excluded.day,
                size_bytes = excluded.size_bytes,
                mtime = excluded.mtime,
                updated_at = excluded.updated_at
            """,
            rows,
        )

    def delete_files(self, paths: Iterable[Path]) -> None:
        rel_paths = []
        for path in paths:
            try:
                rel_paths.append(str(path.relative_to(self._parquet_root)))
            except ValueError:
                rel_paths.append(str(path))
        if not rel_paths:
            return
        placeholders = ",".join("?" for _ in rel_paths)
        self._connection.execute(
            f"DELETE FROM parquet_file_index WHERE path IN ({placeholders})",
            rel_paths,
        )


def insert_raw_payload(connection: sqlite3.Connection, payload: RawPayload) -> int:
    """Insert a raw payload row and return its id."""

    payload_hash = sha256(payload.payload_json.encode("utf-8")).hexdigest()

    cursor = connection.execute(
        """
        INSERT INTO raw_payloads (
            provider,
            endpoint,
            run_at_utc,
            request_url,
            request_params_json,
            request_headers_json,
            response_status,
            response_headers_json,
            payload_json,
            payload_sha256
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            payload.provider,
            payload.endpoint,
            _serialize_datetime(payload.run_at),
            payload.request_url,
            _json_or_none(payload.request_params),
            _json_or_none(payload.request_headers),
            payload.response_status,
            _json_or_none(payload.response_headers),
            payload.payload_json,
            payload_hash,
        ),
    )
    return int(cursor.lastrowid)


def insert_data_points(
    connection: sqlite3.Connection,
    raw_id: int,
    points: Iterable[DataPoint],
) -> None:
    """Insert normalized data points linked to a raw payload."""

    rows = [
        (
            raw_id,
            point.provider,
            point.product_kind,
            point.metric_type,
            point.value_num,
            point.value_text,
            point.unit,
            point.value_raw,
            point.unit_raw,
            _serialize_datetime(point.observed_at),
            _serialize_datetime(point.valid_start),
            _serialize_datetime(point.valid_end),
            _serialize_datetime(point.issued_at),
            _serialize_datetime(point.run_at),
            point.local_day.isoformat() if point.local_day else None,
            point.lead_unit,
            point.lead_offset,
            point.lead_label,
            point.lead_day_index,
            point.latitude,
            point.longitude,
            point.station,
            point.source_field,
            point.quality_flag,
        )
        for point in points
    ]

    if not rows:
        return

    connection.executemany(
        """
        INSERT INTO data_points (
            raw_id,
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
            quality_flag
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        rows,
    )


def already_ran(connection: sqlite3.Connection, run_at: datetime, *, skip_statuses: Sequence[str]) -> bool:
    row = connection.execute(
        "SELECT status FROM run_history WHERE run_at_utc = ?",
        (_serialize_datetime(run_at),),
    ).fetchone()
    if not row:
        return False
    return row[0] in skip_statuses


def upsert_run_history(
    connection: sqlite3.Connection,
    *,
    run_at: datetime,
    run_id: str,
    status: str,
    parquet_exported_at: datetime | None,
    parquet_root: Path | None,
    raw_payloads: int | None,
    data_points: int | None,
) -> None:
    connection.execute(
        """
        INSERT INTO run_history (
            run_at_utc,
            run_id,
            status,
            parquet_exported_at,
            parquet_root,
            raw_payloads,
            data_points,
            updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(run_at_utc) DO UPDATE SET
            run_id = excluded.run_id,
            status = excluded.status,
            parquet_exported_at = excluded.parquet_exported_at,
            parquet_root = excluded.parquet_root,
            raw_payloads = excluded.raw_payloads,
            data_points = excluded.data_points,
            updated_at = excluded.updated_at
        """,
        (
            _serialize_datetime(run_at),
            run_id,
            status,
            _serialize_datetime(parquet_exported_at),
            str(parquet_root) if parquet_root else None,
            raw_payloads,
            data_points,
            _serialize_datetime(datetime.now(timezone.utc)),
        ),
    )


def prunable_run_ats(
    connection: sqlite3.Connection,
    *,
    cutoff_run_at_utc: datetime,
    limit: int,
) -> list[str]:
    rows = connection.execute(
        """
        SELECT run_at_utc
        FROM run_history
        WHERE parquet_exported_at IS NOT NULL
          AND data_points_pruned_at IS NULL
          AND run_at_utc < ?
        ORDER BY run_at_utc ASC
        LIMIT ?
        """,
        (_serialize_datetime(cutoff_run_at_utc), limit),
    ).fetchall()
    return [row[0] for row in rows if row and row[0]]


def prune_data_points_for_runs(connection: sqlite3.Connection, run_at_utc_values: list[str]) -> int:
    if not run_at_utc_values:
        return 0
    placeholders = ",".join("?" for _ in run_at_utc_values)
    cursor = connection.execute(
        f"""
        DELETE FROM data_points
        WHERE run_at_utc IN ({placeholders})
        """,
        run_at_utc_values,
    )
    now = _serialize_datetime(datetime.now(timezone.utc))
    connection.execute(
        f"""
        UPDATE run_history
        SET data_points_pruned_at = ?
        WHERE run_at_utc IN ({placeholders})
          AND data_points_pruned_at IS NULL
        """,
        [now] + run_at_utc_values,
    )
    return cursor.rowcount


def prune_raw_payloads_for_runs(connection: sqlite3.Connection, run_at_utc_values: list[str]) -> int:
    if not run_at_utc_values:
        return 0
    placeholders = ",".join("?" for _ in run_at_utc_values)
    cursor = connection.execute(
        f"""
        DELETE FROM raw_payloads
        WHERE run_at_utc IN ({placeholders})
        """,
        run_at_utc_values,
    )
    now = _serialize_datetime(datetime.now(timezone.utc))
    connection.execute(
        f"""
        UPDATE run_history
        SET raw_payloads_pruned_at = ?
        WHERE run_at_utc IN ({placeholders})
          AND raw_payloads_pruned_at IS NULL
        """,
        [now] + run_at_utc_values,
    )
    return cursor.rowcount


def datapoint_counts_by_run_at(connection: sqlite3.Connection, run_at: datetime) -> dict[tuple[str, str, str, str], int]:
    cursor = connection.execute(
        """
        SELECT provider, product_kind, metric_type, run_at_utc, COUNT(*)
        FROM data_points
        WHERE run_at_utc = ?
        GROUP BY provider, product_kind, metric_type, run_at_utc
        """,
        (_serialize_datetime(run_at),),
    )
    return {(row[0], row[1], row[2], row[3]): row[4] for row in cursor.fetchall()}


def parquet_counts_by_run_at(connection: sqlite3.Connection, run_at: datetime) -> dict[tuple[str, str, str, str], int]:
    cursor = connection.execute(
        """
        SELECT provider, product_kind, metric_type, run_at_utc, count
        FROM parquet_counts
        WHERE run_at_utc = ?
        """,
        (_serialize_datetime(run_at),),
    )
    return {(row[0], row[1], row[2], row[3]): row[4] for row in cursor.fetchall()}


def datapoint_counts_for_runs(
    connection: sqlite3.Connection,
    run_at_utc_values: list[str],
) -> dict[tuple[str, str, str, str], int]:
    if not run_at_utc_values:
        return {}
    placeholders = ",".join("?" for _ in run_at_utc_values)
    cursor = connection.execute(
        f"""
        SELECT provider, product_kind, metric_type, run_at_utc, COUNT(*)
        FROM data_points
        WHERE run_at_utc IN ({placeholders})
        GROUP BY provider, product_kind, metric_type, run_at_utc
        """,
        run_at_utc_values,
    )
    return {(row[0], row[1], row[2], row[3]): row[4] for row in cursor.fetchall()}


def parquet_counts_for_runs(
    connection: sqlite3.Connection,
    run_at_utc_values: list[str],
) -> dict[tuple[str, str, str, str], int]:
    if not run_at_utc_values:
        return {}
    placeholders = ",".join("?" for _ in run_at_utc_values)
    cursor = connection.execute(
        f"""
        SELECT provider, product_kind, metric_type, run_at_utc, count
        FROM parquet_counts
        WHERE run_at_utc IN ({placeholders})
        """,
        run_at_utc_values,
    )
    return {(row[0], row[1], row[2], row[3]): row[4] for row in cursor.fetchall()}


def parquet_counts_totals(
    connection: sqlite3.Connection,
    run_at_utc_values: list[str],
) -> dict[str, int]:
    if not run_at_utc_values:
        return {}
    placeholders = ",".join("?" for _ in run_at_utc_values)
    cursor = connection.execute(
        f"""
        SELECT run_at_utc, SUM(count)
        FROM parquet_counts
        WHERE run_at_utc IN ({placeholders})
        GROUP BY run_at_utc
        """,
        run_at_utc_values,
    )
    return {row[0]: row[1] for row in cursor.fetchall()}


def run_history_point_counts(
    connection: sqlite3.Connection,
    run_at_utc_values: list[str],
) -> dict[str, int]:
    if not run_at_utc_values:
        return {}
    placeholders = ",".join("?" for _ in run_at_utc_values)
    cursor = connection.execute(
        f"""
        SELECT run_at_utc, COALESCE(data_points, 0)
        FROM run_history
        WHERE run_at_utc IN ({placeholders})
        """,
        run_at_utc_values,
    )
    return {row[0]: row[1] for row in cursor.fetchall()}


def write_parquet_counts(
    connection: sqlite3.Connection,
    *,
    run_at: datetime,
    counts: dict[tuple[str, str, str, str], int],
) -> None:
    run_at_value = _serialize_datetime(run_at)
    if run_at_value is None:
        return
    connection.execute(
        "DELETE FROM parquet_counts WHERE run_at_utc = ?",
        (run_at_value,),
    )
    if not counts:
        return
    rows = [
        (run_at_value, provider, product_kind, metric_type, count, _serialize_datetime(datetime.now(timezone.utc)))
        for (provider, product_kind, metric_type, _), count in counts.items()
        if count is not None
    ]
    connection.executemany(
        """
        INSERT INTO parquet_counts (run_at_utc, provider, product_kind, metric_type, count, updated_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        rows,
    )


def rebuild_parquet_index(connection: sqlite3.Connection, *, parquet_root: Path) -> int:
    connection.execute("DELETE FROM parquet_file_index")
    records: list[ParquetFileRecord] = []
    for path in parquet_root.rglob("*.parquet"):
        if path.name.startswith(".") or path.name.endswith(".tmp"):
            continue
        day_tag = None
        for part in path.parts:
            if part.startswith("day="):
                day_tag = part.split("=", 1)[1]
                break
        if day_tag is None:
            day_token = "day="
            if day_token in path.name:
                day_tag = path.name.split(day_token, 1)[1].split("-", 1)[0]
        if day_tag is None:
            continue
        if len(day_tag) != 8:
            continue
        day = f"{day_tag[0:4]}-{day_tag[4:6]}-{day_tag[6:8]}"
        stat = path.stat()
        records.append(
            ParquetFileRecord(
                path=path,
                provider=INDEX_ALL,
                product_kind=INDEX_ALL,
                metric_type=INDEX_ALL,
                day=day,
                size_bytes=stat.st_size,
                mtime=int(stat.st_mtime),
            )
        )
    writer = SqliteParquetIndexWriter(connection, parquet_root=parquet_root)
    writer.record_files(records)
    return len(records)


def list_unsynced_parquet_files(
    connection: sqlite3.Connection,
    *,
    target: str,
    min_mtime: int | None = None,
    day: str | None = None,
    provider: str | None = None,
    product_kind: str | None = None,
    metric_type: str | None = None,
    path_prefix: str | None = None,
    compacted_only: bool = False,
) -> list[ParquetIndexRow]:
    clauses = ["sync.target IS NULL"]
    params: list[object] = [target]
    if min_mtime is not None:
        clauses.append("idx.mtime <= ?")
        params.append(min_mtime)
    if day is not None:
        clauses.append("idx.day = ?")
        params.append(day)
    if provider is not None:
        clauses.append("idx.provider = ?")
        params.append(provider)
    if product_kind is not None:
        clauses.append("idx.product_kind = ?")
        params.append(product_kind)
    if metric_type is not None:
        clauses.append("idx.metric_type = ?")
        params.append(metric_type)
    if path_prefix is not None:
        clauses.append("idx.path LIKE ?")
        params.append(f"{path_prefix}%")
    if compacted_only:
        clauses.append("idx.path LIKE ?")
        params.append("%/compact-%")
    where_clause = " AND ".join(clauses)
    cursor = connection.execute(
        f"""
        SELECT idx.path, idx.provider, idx.product_kind, idx.metric_type, idx.day, idx.size_bytes, idx.mtime
        FROM parquet_file_index idx
        LEFT JOIN parquet_sync sync
          ON sync.target = ?
         AND sync.path = idx.path
         AND sync.size_bytes = idx.size_bytes
         AND sync.mtime = idx.mtime
        WHERE {where_clause}
        ORDER BY idx.path
        """,
        params,
    )
    return [
        ParquetIndexRow(
            path=row[0],
            provider=row[1],
            product_kind=row[2],
            metric_type=row[3],
            day=row[4],
            size_bytes=row[5],
            mtime=row[6],
        )
        for row in cursor.fetchall()
    ]


def record_parquet_sync_results(
    connection: sqlite3.Connection,
    *,
    target: str,
    rows: Iterable[ParquetIndexRow],
    status: str,
    error: str | None,
) -> None:
    now = _serialize_datetime(datetime.now(timezone.utc))
    payload = [
        (target, row.path, row.size_bytes, row.mtime, now, status, error)
        for row in rows
    ]
    if not payload:
        return
    connection.executemany(
        """
        INSERT INTO parquet_sync (
            target, path, size_bytes, mtime, synced_at, status, error
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(target, path, size_bytes, mtime) DO UPDATE SET
            synced_at = excluded.synced_at,
            status = excluded.status,
            error = excluded.error
        """,
        payload,
    )


def _serialize_datetime(value: Optional[datetime]) -> Optional[str]:
    if value is None:
        return None
    return value.isoformat()


def _json_or_none(value: Optional[Mapping[str, str]]) -> Optional[str]:
    if value is None:
        return None
    return json.dumps(value, sort_keys=True)


def _ensure_column(connection: sqlite3.Connection, table: str, column: str, column_type: str) -> None:
    columns = {row[1] for row in connection.execute(f"PRAGMA table_info({table})")}
    if column in columns:
        return
    connection.execute(f"ALTER TABLE {table} ADD COLUMN {column} {column_type}")


__all__ = [
    "DEFAULT_DB_PATH",
    "ParquetIndexRow",
    "RawPayload",
    "SqliteParquetIndexWriter",
    "SqliteDataPointWriter",
    "already_ran",
    "prune_data_points_for_runs",
    "prune_raw_payloads_for_runs",
    "prunable_run_ats",
    "datapoint_counts_by_run_at",
    "parquet_counts_by_run_at",
    "datapoint_counts_for_runs",
    "parquet_counts_for_runs",
    "parquet_counts_totals",
    "run_history_point_counts",
    "write_parquet_counts",
    "rebuild_parquet_index",
    "list_unsynced_parquet_files",
    "record_parquet_sync_results",
    "open_database",
    "ensure_schema",
    "insert_raw_payload",
    "insert_data_points",
    "upsert_run_history",
]
