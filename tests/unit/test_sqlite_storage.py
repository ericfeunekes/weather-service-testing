from __future__ import annotations

from datetime import datetime, timezone

from wxbench.domain.datapoints import observation_to_datapoints
from wxbench.domain.models import Location, Observation
from wxbench.storage.sqlite import RawPayload, ensure_schema, insert_data_points, insert_raw_payload, open_database


def test_sqlite_storage_inserts_raw_and_points(tmp_path):
    db_path = tmp_path / "wxbench.sqlite"
    connection = open_database(db_path)
    ensure_schema(connection)

    observed_at = datetime(2024, 1, 1, 12, tzinfo=timezone.utc)
    run_at = datetime(2024, 1, 1, 13, tzinfo=timezone.utc)
    observation = Observation(
        provider="demo",
        station="station-a",
        location=Location(latitude=10.0, longitude=20.0),
        observed_at=observed_at,
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
            request_params={"lat": "10", "lon": "20"},
            request_headers={"accept": "application/json"},
            response_status=200,
            response_headers={"content-type": "application/json"},
            payload_json="{}",
        ),
    )
    insert_data_points(connection, raw_id, points)
    connection.commit()

    raw_count = connection.execute("SELECT COUNT(*) FROM raw_payloads").fetchone()[0]
    point_count = connection.execute("SELECT COUNT(*) FROM data_points").fetchone()[0]

    assert raw_count == 1
    assert point_count == len(points)

    connection.close()
