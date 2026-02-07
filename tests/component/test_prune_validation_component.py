from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import sqlite3

from wxbench.domain.datapoints import observation_to_datapoints
from wxbench.domain.models import Location, Observation
from wxbench.runtime import _validate_prune_window
from wxbench.storage.parquet import ParquetDataPointWriter, resolve_parquet_root
from wxbench.storage.sqlite import RawPayload, ensure_schema, insert_data_points, insert_raw_payload, open_database


def _seed_run(connection: sqlite3.Connection, *, run_at: datetime) -> tuple[int, list]:
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
    return raw_id, points


def test_prune_validation_matches_parquet_and_sqlite(tmp_path: Path) -> None:
    db_path = tmp_path / "wxbench.sqlite"
    connection = open_database(db_path)
    ensure_schema(connection)

    run_one = datetime(2025, 12, 29, 13, tzinfo=timezone.utc)
    run_two = datetime(2026, 1, 24, 10, tzinfo=timezone.utc)
    raw_one, points_one = _seed_run(connection, run_at=run_one)
    raw_two, points_two = _seed_run(connection, run_at=run_two)
    connection.commit()

    parquet_root = resolve_parquet_root(tmp_path)
    writer_one = ParquetDataPointWriter(parquet_root, run_id="test-run-one")
    writer_one.write(raw_one, points_one, run_at=run_one)
    writer_two = ParquetDataPointWriter(parquet_root, run_id="test-run-two")
    writer_two.write(raw_two, points_two, run_at=run_two)

    logs_path = tmp_path / "logs.jsonl"
    validated = _validate_prune_window(
        connection=connection,
        run_at_utc_values=[run_one.isoformat(), run_two.isoformat()],
        logs_path=logs_path,
        parquet_root=parquet_root,
    )
    assert validated == [run_one.isoformat(), run_two.isoformat()]

    for path in parquet_root.rglob("*.parquet"):
        if "test-run-one" in path.name:
            path.unlink(missing_ok=True)

    blocked = _validate_prune_window(
        connection=connection,
        run_at_utc_values=[run_one.isoformat()],
        logs_path=logs_path,
        parquet_root=parquet_root,
    )
    assert blocked == []
    assert "prune_validation_failed" in logs_path.read_text()

    connection.close()


def test_prune_validation_continues_past_bad_run(tmp_path: Path) -> None:
    """One bad run should not block pruning of other valid runs."""
    db_path = tmp_path / "wxbench.sqlite"
    connection = open_database(db_path)
    ensure_schema(connection)

    run_good = datetime(2025, 12, 29, 13, tzinfo=timezone.utc)
    run_bad = datetime(2026, 1, 10, 10, tzinfo=timezone.utc)
    run_good2 = datetime(2026, 1, 24, 10, tzinfo=timezone.utc)

    raw_good, points_good = _seed_run(connection, run_at=run_good)
    raw_bad, points_bad = _seed_run(connection, run_at=run_bad)
    raw_good2, points_good2 = _seed_run(connection, run_at=run_good2)
    connection.commit()

    parquet_root = resolve_parquet_root(tmp_path)
    writer_good = ParquetDataPointWriter(parquet_root, run_id="test-run-good")
    writer_good.write(raw_good, points_good, run_at=run_good)
    writer_bad = ParquetDataPointWriter(parquet_root, run_id="test-run-bad")
    writer_bad.write(raw_bad, points_bad, run_at=run_bad)
    writer_good2 = ParquetDataPointWriter(parquet_root, run_id="test-run-good2")
    writer_good2.write(raw_good2, points_good2, run_at=run_good2)

    # Remove parquet files for the "bad" run to simulate a mismatch
    for path in parquet_root.rglob("*.parquet"):
        if "test-run-bad" in path.name:
            path.unlink(missing_ok=True)

    logs_path = tmp_path / "logs.jsonl"
    validated = _validate_prune_window(
        connection=connection,
        run_at_utc_values=[run_good.isoformat(), run_bad.isoformat(), run_good2.isoformat()],
        logs_path=logs_path,
        parquet_root=parquet_root,
    )

    # The bad run should be excluded but the two good runs should still validate
    assert run_good.isoformat() in validated
    assert run_good2.isoformat() in validated
    assert run_bad.isoformat() not in validated
    assert len(validated) == 2

    connection.close()
