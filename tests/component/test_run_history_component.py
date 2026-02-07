from __future__ import annotations

from datetime import datetime, timedelta, timezone

from wxbench.domain.datapoints import observation_to_datapoints
from wxbench.domain.models import Location, Observation
from wxbench.storage.sqlite import (
    RawPayload,
    already_ran,
    datapoint_counts_by_run_at,
    ensure_schema,
    insert_data_points,
    insert_raw_payload,
    open_database,
    parquet_counts_by_run_at,
    prune_data_points_for_runs,
    prune_raw_payloads_for_runs,
    prunable_run_ats,
    upsert_run_history,
    write_parquet_counts,
)


def test_run_history_skip_logic(tmp_path):
    db_path = tmp_path / "wxbench.sqlite"
    connection = open_database(db_path)
    ensure_schema(connection)

    run_at = datetime(2024, 1, 1, 12, tzinfo=timezone.utc)
    upsert_run_history(
        connection,
        run_at=run_at,
        run_id="run-1",
        status="success",
        parquet_exported_at=run_at,
        parquet_root=tmp_path,
        raw_payloads=1,
        data_points=1,
    )
    connection.commit()

    assert already_ran(connection, run_at, skip_statuses=("success", "partial", "no_data"))
    assert not already_ran(connection, run_at, skip_statuses=("partial",))

    connection.close()


def test_pruning_respects_parquet_export(tmp_path):
    db_path = tmp_path / "wxbench.sqlite"
    connection = open_database(db_path)
    ensure_schema(connection)

    now = datetime(2024, 1, 8, 12, tzinfo=timezone.utc)
    old_run = now - timedelta(days=2)
    very_old_run = now - timedelta(days=8)

    observation = Observation(
        provider="demo",
        station="station-a",
        location=Location(latitude=10.0, longitude=20.0),
        observed_at=old_run,
        temperature_c=20.0,
    )
    points = observation_to_datapoints(observation, run_at=old_run, tz_name="UTC")

    raw_id_old = insert_raw_payload(
        connection,
        RawPayload(
            provider="demo",
            endpoint="observation",
            run_at=old_run,
            request_url="https://example.test",
            request_params=None,
            request_headers=None,
            response_status=200,
            response_headers=None,
            payload_json="{}",
        ),
    )
    insert_data_points(connection, raw_id_old, points)

    raw_id_very_old = insert_raw_payload(
        connection,
        RawPayload(
            provider="demo",
            endpoint="observation",
            run_at=very_old_run,
            request_url="https://example.test",
            request_params=None,
            request_headers=None,
            response_status=200,
            response_headers=None,
            payload_json="{}",
        ),
    )
    insert_data_points(connection, raw_id_very_old, points)

    upsert_run_history(
        connection,
        run_at=old_run,
        run_id="run-old",
        status="success",
        parquet_exported_at=now,
        parquet_root=tmp_path,
        raw_payloads=1,
        data_points=len(points),
    )
    upsert_run_history(
        connection,
        run_at=very_old_run,
        run_id="run-very-old",
        status="success",
        parquet_exported_at=now,
        parquet_root=tmp_path,
        raw_payloads=1,
        data_points=len(points),
    )
    connection.commit()

    candidates_points = prunable_run_ats(connection, cutoff_run_at_utc=now - timedelta(hours=24), limit=10)
    candidates_raw = prunable_run_ats(connection, cutoff_run_at_utc=now - timedelta(days=7), limit=10)
    pruned_points = prune_data_points_for_runs(connection, candidates_points)
    pruned_raw = prune_raw_payloads_for_runs(connection, candidates_raw)
    connection.commit()

    remaining_points = connection.execute("SELECT COUNT(*) FROM data_points").fetchone()[0]
    remaining_raw = connection.execute("SELECT COUNT(*) FROM raw_payloads").fetchone()[0]

    assert pruned_points > 0
    assert pruned_raw > 0
    assert remaining_points == 0
    assert remaining_raw == 1

    connection.close()


def test_sqlite_counts_by_run_at(tmp_path):
    db_path = tmp_path / "wxbench.sqlite"
    connection = open_database(db_path)
    ensure_schema(connection)

    run_at = datetime(2024, 1, 2, 10, tzinfo=timezone.utc)
    observation = Observation(
        provider="demo",
        station="station-a",
        location=Location(latitude=10.0, longitude=20.0),
        observed_at=run_at,
        temperature_c=18.0,
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
    connection.commit()

    counts = datapoint_counts_by_run_at(connection, run_at)
    assert counts

    connection.close()


def test_write_parquet_counts(tmp_path):
    db_path = tmp_path / "wxbench.sqlite"
    connection = open_database(db_path)
    ensure_schema(connection)

    run_at = datetime(2024, 1, 2, 10, tzinfo=timezone.utc)
    counts = {("demo", "observation", "temperature", run_at.isoformat()): 3}
    write_parquet_counts(connection, run_at=run_at, counts=counts)
    connection.commit()

    parquet_grouped = parquet_counts_by_run_at(connection, run_at)
    assert parquet_grouped == counts

    connection.close()
