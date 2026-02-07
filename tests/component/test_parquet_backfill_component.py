from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import sqlite3

from wxbench.domain.datapoints import observation_to_datapoints
from wxbench.domain.models import Location, Observation
from wxbench.parquet_backfill import run_backfill, run_backfill_single
from wxbench.storage.parquet import datapoint_counts_by_run_at as parquet_counts
from wxbench.storage.sqlite import (
    RawPayload,
    datapoint_counts_by_run_at as sqlite_counts,
    ensure_schema,
    insert_data_points,
    insert_raw_payload,
    open_database,
    parquet_counts_by_run_at,
)


def _seed_run(connection: sqlite3.Connection, *, run_at: datetime) -> None:
    observation = Observation(
        provider="demo",
        station="station-a",
        location=Location(latitude=10.0, longitude=20.0),
        observed_at=run_at,
        temperature_c=20.0,
    )
    points = observation_to_datapoints(observation, run_at=run_at, tz_name="UTC")
    raw_id = insert_raw_payload(
        connection,
        RawPayload(
            provider="demo",
            endpoint="observation",
            run_at=run_at,
            request_url="https://example.test",
            request_params=None,
            request_headers=None,
            response_status=200,
            response_headers=None,
            payload_json="{}",
        ),
    )
    insert_data_points(connection, raw_id, points)


def test_backfill_single_matches_sqlite_counts(tmp_path: Path) -> None:
    db_path = tmp_path / "wxbench.sqlite"
    connection = open_database(db_path)
    ensure_schema(connection)

    run_one = datetime(2025, 12, 29, 13, tzinfo=timezone.utc)
    run_two = datetime(2026, 1, 24, 10, tzinfo=timezone.utc)
    _seed_run(connection, run_at=run_one)
    _seed_run(connection, run_at=run_two)
    connection.commit()
    connection.close()

    for run_at in (run_one, run_two):
        run_backfill_single(db_path=db_path, data_root=tmp_path, run_at_str=run_at.isoformat())
        run_backfill_single(db_path=db_path, data_root=tmp_path, run_at_str=run_at.isoformat())

        connection = open_database(db_path)
        sqlite_grouped = sqlite_counts(connection, run_at)
        parquet_grouped = parquet_counts(tmp_path / "parquet", run_at)
        parquet_table_grouped = parquet_counts_by_run_at(connection, run_at)
        connection.close()

        assert sqlite_grouped == parquet_grouped
        assert parquet_grouped == parquet_table_grouped


def test_backfill_all_is_idempotent(tmp_path: Path) -> None:
    db_path = tmp_path / "wxbench.sqlite"
    connection = open_database(db_path)
    ensure_schema(connection)

    run_one = datetime(2025, 12, 29, 13, tzinfo=timezone.utc)
    run_two = datetime(2026, 1, 24, 10, tzinfo=timezone.utc)
    _seed_run(connection, run_at=run_one)
    _seed_run(connection, run_at=run_two)
    connection.commit()
    connection.close()

    run_backfill(db_path=db_path, data_root=tmp_path)
    run_backfill(db_path=db_path, data_root=tmp_path)

    for run_at in (run_one, run_two):
        connection = open_database(db_path)
        sqlite_grouped = sqlite_counts(connection, run_at)
        parquet_grouped = parquet_counts(tmp_path / "parquet", run_at)
        connection.close()

        assert sqlite_grouped == parquet_grouped
