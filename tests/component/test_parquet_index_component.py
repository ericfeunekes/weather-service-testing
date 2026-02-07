from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from wxbench.domain.datapoints import observation_to_datapoints
from wxbench.domain.models import Location, Observation
from wxbench.storage.parquet import INDEX_ALL, ParquetDataPointWriter
from wxbench.storage.sqlite import (
    ParquetIndexRow,
    SqliteParquetIndexWriter,
    ensure_schema,
    list_unsynced_parquet_files,
    open_database,
    record_parquet_sync_results,
    rebuild_parquet_index,
)


def test_index_writer_records_and_deletes(tmp_path: Path) -> None:
    parquet_root = tmp_path / "parquet"
    db_path = tmp_path / "wxbench.sqlite"
    connection = open_database(db_path)
    ensure_schema(connection)

    index_writer = SqliteParquetIndexWriter(connection, parquet_root=parquet_root)
    run_at = datetime(2024, 1, 1, 12, tzinfo=timezone.utc)
    observation = Observation(
        provider="demo",
        station="station-a",
        location=Location(latitude=10.0, longitude=20.0),
        observed_at=run_at,
        temperature_c=20.0,
    )
    points = observation_to_datapoints(observation, run_at=run_at, tz_name="UTC")
    writer = ParquetDataPointWriter(parquet_root, run_id="test-run", index_writer=index_writer)
    writer.write(1, points, run_at=run_at)
    connection.commit()

    row = connection.execute("SELECT path FROM parquet_file_index").fetchone()
    assert row is not None
    assert not row[0].startswith("/")

    file_path = next(parquet_root.rglob("*.parquet"))
    index_writer.delete_files([file_path])
    connection.commit()
    remaining = connection.execute("SELECT COUNT(*) FROM parquet_file_index").fetchone()[0]
    assert remaining == 0
    connection.close()


def test_rebuild_parquet_index(tmp_path: Path) -> None:
    parquet_root = tmp_path / "parquet"
    db_path = tmp_path / "wxbench.sqlite"
    connection = open_database(db_path)
    ensure_schema(connection)

    run_at = datetime(2024, 1, 2, 12, tzinfo=timezone.utc)
    observation = Observation(
        provider="demo",
        station="station-a",
        location=Location(latitude=10.0, longitude=20.0),
        observed_at=run_at,
        temperature_c=19.0,
    )
    points = observation_to_datapoints(observation, run_at=run_at, tz_name="UTC")
    writer = ParquetDataPointWriter(parquet_root, run_id="test-run")
    writer.write(1, points, run_at=run_at)

    count = rebuild_parquet_index(connection, parquet_root=parquet_root)
    connection.commit()
    assert count > 0
    connection.close()


def test_sync_ledger_marks_rows(tmp_path: Path) -> None:
    db_path = tmp_path / "wxbench.sqlite"
    connection = open_database(db_path)
    ensure_schema(connection)

    row = ParquetIndexRow(
        path="day=20240101/part.parquet",
        provider=INDEX_ALL,
        product_kind=INDEX_ALL,
        metric_type=INDEX_ALL,
        day="2024-01-01",
        size_bytes=123,
        mtime=1000,
    )
    connection.execute(
        """
        INSERT INTO parquet_file_index (path, provider, product_kind, metric_type, day, size_bytes, mtime, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (row.path, row.provider, row.product_kind, row.metric_type, row.day, row.size_bytes, row.mtime, datetime.now(timezone.utc).isoformat()),
    )
    connection.commit()

    unsynced = list_unsynced_parquet_files(connection, target="demo-target")
    assert unsynced

    record_parquet_sync_results(connection, target="demo-target", rows=unsynced, status="ok", error=None)
    connection.commit()

    unsynced_after = list_unsynced_parquet_files(connection, target="demo-target")
    assert unsynced_after == []
    connection.close()
