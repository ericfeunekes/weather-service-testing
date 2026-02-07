from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pyarrow.parquet as pq
import pytest

from wxbench.domain.datapoints import observation_to_datapoints
from wxbench.domain.models import Location, Observation
from wxbench.storage.parquet import ParquetDataPointWriter, compact_partitions, datapoint_counts_by_run_at


def test_parquet_writer_creates_partitioned_files(tmp_path):
    parquet_root = tmp_path / "parquet"
    run_at = datetime(2024, 1, 1, 13, tzinfo=timezone.utc)
    observation = Observation(
        provider="demo",
        station="station-a",
        location=Location(latitude=10.0, longitude=20.0),
        observed_at=datetime(2024, 1, 1, 12, tzinfo=timezone.utc),
        temperature_c=20.0,
    )
    points = observation_to_datapoints(observation, run_at=run_at, tz_name="UTC")

    writer = ParquetDataPointWriter(parquet_root, run_id="test-run")
    count = writer.write(1, points, run_at=run_at)

    files = list(parquet_root.rglob("*.parquet"))
    assert count == len(points)
    assert files

    table = pq.ParquetFile(files[0]).read()
    assert table.num_rows == len(points)


def test_compaction_merges_day_files(tmp_path):
    parquet_root = tmp_path / "parquet"
    run_at = datetime(2024, 1, 2, 9, tzinfo=timezone.utc)
    observation = Observation(
        provider="demo",
        station="station-a",
        location=Location(latitude=10.0, longitude=20.0),
        observed_at=datetime(2024, 1, 2, 8, tzinfo=timezone.utc),
        temperature_c=18.0,
    )
    points = observation_to_datapoints(observation, run_at=run_at, tz_name="UTC")

    writer = ParquetDataPointWriter(parquet_root, run_id="test-run")
    writer.write(1, points, run_at=run_at)
    writer.write(2, points, run_at=run_at)

    results = compact_partitions(writer.touched_partitions(), run_id="test-run")
    assert len(results) == 1
    assert results[0].status == "success"

    files = list(parquet_root.rglob("*.parquet"))
    assert len(files) == 1


def test_parquet_counts_by_run_at(tmp_path):
    parquet_root = tmp_path / "parquet"
    run_at = datetime(2024, 1, 3, 10, tzinfo=timezone.utc)
    observation = Observation(
        provider="demo",
        station="station-a",
        location=Location(latitude=10.0, longitude=20.0),
        observed_at=datetime(2024, 1, 3, 9, tzinfo=timezone.utc),
        temperature_c=12.0,
    )
    points = observation_to_datapoints(observation, run_at=run_at, tz_name="UTC")

    writer = ParquetDataPointWriter(parquet_root, run_id="test-run")
    writer.write(1, points, run_at=run_at)

    counts = datapoint_counts_by_run_at(parquet_root, run_at)
    assert counts


def test_parquet_writer_rejects_mismatched_run_at(tmp_path):
    parquet_root = tmp_path / "parquet"
    run_at = datetime(2024, 1, 4, 10, tzinfo=timezone.utc)
    wrong_run_at = run_at + timedelta(hours=1)
    observation = Observation(
        provider="demo",
        station="station-a",
        location=Location(latitude=10.0, longitude=20.0),
        observed_at=wrong_run_at,
        temperature_c=12.0,
    )
    points = observation_to_datapoints(observation, run_at=wrong_run_at, tz_name="UTC")

    writer = ParquetDataPointWriter(parquet_root, run_id="test-run")
    with pytest.raises(ValueError):
        writer.write(1, points, run_at=run_at)


def test_compaction_skips_when_unreadable_file_present(tmp_path):
    parquet_root = tmp_path / "parquet"
    run_at = datetime(2024, 1, 5, 9, tzinfo=timezone.utc)
    observation = Observation(
        provider="demo",
        station="station-a",
        location=Location(latitude=10.0, longitude=20.0),
        observed_at=datetime(2024, 1, 5, 8, tzinfo=timezone.utc),
        temperature_c=18.0,
    )
    points = observation_to_datapoints(observation, run_at=run_at, tz_name="UTC")

    writer = ParquetDataPointWriter(parquet_root, run_id="test-run")
    writer.write(1, points, run_at=run_at)
    writer.write(2, points, run_at=run_at)

    partition = next(iter(writer.touched_partitions()))
    corrupt_path = partition.path / f"part-test-run-day={partition.day}-corrupt.parquet"
    corrupt_path.write_text("not parquet")

    results = compact_partitions(writer.touched_partitions(), run_id="test-run")
    assert len(results) == 1
    assert results[0].status == "failed"
    files = list(parquet_root.rglob("*.parquet"))
    assert len(files) == 3


def test_compaction_skips_when_over_max_bytes(tmp_path):
    parquet_root = tmp_path / "parquet"
    run_at = datetime(2024, 1, 6, 9, tzinfo=timezone.utc)
    observation = Observation(
        provider="demo",
        station="station-a",
        location=Location(latitude=10.0, longitude=20.0),
        observed_at=datetime(2024, 1, 6, 8, tzinfo=timezone.utc),
        temperature_c=18.0,
    )
    points = observation_to_datapoints(observation, run_at=run_at, tz_name="UTC")

    writer = ParquetDataPointWriter(parquet_root, run_id="test-run")
    writer.write(1, points, run_at=run_at)
    writer.write(2, points, run_at=run_at)

    results = compact_partitions(writer.touched_partitions(), run_id="test-run", max_bytes=1)
    assert len(results) == 1
    assert results[0].status == "skipped"
    files = list(parquet_root.rglob("*.parquet"))
    assert len(files) == 2


def test_compaction_noop_with_single_file(tmp_path):
    parquet_root = tmp_path / "parquet"
    run_at = datetime(2024, 1, 7, 9, tzinfo=timezone.utc)
    observation = Observation(
        provider="demo",
        station="station-a",
        location=Location(latitude=10.0, longitude=20.0),
        observed_at=datetime(2024, 1, 7, 8, tzinfo=timezone.utc),
        temperature_c=18.0,
    )
    points = observation_to_datapoints(observation, run_at=run_at, tz_name="UTC")

    writer = ParquetDataPointWriter(parquet_root, run_id="test-run")
    writer.write(1, points, run_at=run_at)

    results = compact_partitions(writer.touched_partitions(), run_id="test-run")
    assert len(results) == 1
    assert results[0].status == "skipped"
    files = list(parquet_root.rglob("*.parquet"))
    assert len(files) == 1


def test_compaction_force_single_rewrites_file(tmp_path):
    parquet_root = tmp_path / "parquet"
    run_at = datetime(2024, 1, 8, 9, tzinfo=timezone.utc)
    observation = Observation(
        provider="demo",
        station="station-a",
        location=Location(latitude=10.0, longitude=20.0),
        observed_at=datetime(2024, 1, 8, 8, tzinfo=timezone.utc),
        temperature_c=18.0,
    )
    points = observation_to_datapoints(observation, run_at=run_at, tz_name="UTC")

    writer = ParquetDataPointWriter(parquet_root, run_id="test-run")
    writer.write(1, points, run_at=run_at)

    results = compact_partitions(writer.touched_partitions(), run_id="test-run", force_single=True)
    assert len(results) == 1
    assert results[0].status == "success"

    files = list(parquet_root.rglob("*.parquet"))
    assert len(files) == 1
    assert files[0].name.startswith("compact-")


def test_parquet_counts_filters_by_run_at(tmp_path):
    parquet_root = tmp_path / "parquet"
    run_at = datetime(2024, 1, 8, 10, tzinfo=timezone.utc)
    later_run = run_at + timedelta(hours=1)
    observation = Observation(
        provider="demo",
        station="station-a",
        location=Location(latitude=10.0, longitude=20.0),
        observed_at=datetime(2024, 1, 8, 9, tzinfo=timezone.utc),
        temperature_c=12.0,
    )
    points = observation_to_datapoints(observation, run_at=run_at, tz_name="UTC")
    later_points = observation_to_datapoints(observation, run_at=later_run, tz_name="UTC")

    writer = ParquetDataPointWriter(parquet_root, run_id="test-run")
    writer.write(1, points, run_at=run_at)
    writer.write(2, later_points, run_at=later_run)

    counts = datapoint_counts_by_run_at(parquet_root, run_at)
    assert counts
    assert all(key[3] == run_at.isoformat() for key in counts)
