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
    def __init__(self) -> None:
        self.paths: list[str] = []

    def sync(self, *, source_root: Path, target: str, paths: list[str]):  # noqa: ANN001
        self.paths.extend(paths)
        return 0, None


def test_run_sync_records_ledger(tmp_path: Path) -> None:
    data_root = tmp_path
    parquet_root = tmp_path / "parquet"
    db_path = tmp_path / "wxbench.sqlite"
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
