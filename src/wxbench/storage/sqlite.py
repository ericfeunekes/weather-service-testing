"""SQLite storage for raw payloads and normalized data points."""
from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import date, datetime
from hashlib import sha256
from pathlib import Path
from typing import Iterable, Mapping, Optional

from wxbench.domain.models import DataPoint


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


def open_database(path: Path | None = None) -> sqlite3.Connection:
    """Open a SQLite database connection (creates file if missing)."""

    target = path or DEFAULT_DB_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(target)


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
        """
    )
    _ensure_column(connection, "data_points", "lead_day_index", "INTEGER")


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
    "RawPayload",
    "open_database",
    "ensure_schema",
    "insert_raw_payload",
    "insert_data_points",
]
