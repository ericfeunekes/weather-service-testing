from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from wxbench.domain.datapoints import observation_to_datapoints
from wxbench.domain.models import Location, Observation
from wxbench.storage.parquet import ParquetDataPointWriter
from wxbench.storage.sqlite import (
    SqliteParquetIndexWriter,
    ensure_schema,
    list_unsynced_parquet_files,
    open_database,
)
from wxbench.sync_parquet import run_sync


class FakeTransport:
    def __init__(self, *, return_code: int = 0) -> None:
        self.paths: list[str] = []
        self.return_code = return_code

    def sync(self, *, source_root: Path, target: str, paths: list[str]):  # noqa: ANN001
        self.paths.extend(paths)
        error = None if self.return_code == 0 else "transport failed"
        return self.return_code, error


def _seed_parquet_file(data_root: Path) -> Path:
    parquet_root = data_root / "parquet"
    db_path = data_root / "wxbench.sqlite"
    connection = open_database(db_path)
    ensure_schema(connection)

    index_writer = SqliteParquetIndexWriter(connection, parquet_root=parquet_root)
    run_at = datetime(2024, 1, 3, 12, tzinfo=timezone.utc)
    observation = Observation(
        provider="demo",
        station="station-a",
        location=Location(latitude=10.0, longitude=20.0),
        observed_at=run_at,
        temperature_c=21.0,
    )
    points = observation_to_datapoints(observation, run_at=run_at, tz_name="UTC")
    writer = ParquetDataPointWriter(parquet_root, run_id="test-run", index_writer=index_writer)
    writer.write(1, points, run_at=run_at)
    connection.commit()
    connection.close()
    return db_path


def test_run_sync_records_ledger(tmp_path: Path) -> None:
    data_root = tmp_path
    db_path = _seed_parquet_file(data_root)

    transport = FakeTransport()
    result = run_sync(
        data_root=data_root,
        db_path=db_path,
        target="demo-target",
        compacted_only=False,
        transport=transport,
    )
    assert result == 0
    assert transport.paths

    connection = open_database(db_path)
    ensure_schema(connection)
    unsynced = list_unsynced_parquet_files(connection, target="demo-target")
    connection.close()
    assert unsynced == []


def test_failed_sync_remains_eligible_for_retry(tmp_path: Path) -> None:
    data_root = tmp_path
    db_path = _seed_parquet_file(data_root)

    failed_transport = FakeTransport(return_code=2)
    assert run_sync(
        data_root=data_root,
        db_path=db_path,
        target="demo-target",
        compacted_only=False,
        transport=failed_transport,
    ) == 2

    connection = open_database(db_path)
    ensure_schema(connection)
    retryable = list_unsynced_parquet_files(connection, target="demo-target")
    connection.close()
    assert retryable

    successful_transport = FakeTransport()
    assert run_sync(
        data_root=data_root,
        db_path=db_path,
        target="demo-target",
        compacted_only=False,
        transport=successful_transport,
    ) == 0
    assert successful_transport.paths == failed_transport.paths

    connection = open_database(db_path)
    ensure_schema(connection)
    assert list_unsynced_parquet_files(connection, target="demo-target") == []
    statuses = connection.execute(
        "SELECT DISTINCT status FROM parquet_sync WHERE target = ?", ("demo-target",)
    ).fetchall()
    connection.close()
    assert statuses == [("ok",)]


def test_dry_run_does_not_write_sync_ledger(tmp_path: Path) -> None:
    data_root = tmp_path
    db_path = _seed_parquet_file(data_root)

    transport = FakeTransport()
    assert run_sync(
        data_root=data_root,
        db_path=db_path,
        target="demo-target",
        compacted_only=False,
        dry_run=True,
        transport=transport,
    ) == 0

    connection = open_database(db_path)
    ensure_schema(connection)
    assert list_unsynced_parquet_files(connection, target="demo-target")
    ledger_count = connection.execute("SELECT COUNT(*) FROM parquet_sync").fetchone()[0]
    connection.close()
    assert ledger_count == 0
