from __future__ import annotations

from datetime import datetime, timezone

from wxbench.parquet_backfill import _parse_date, _parse_datetime, _row_to_datapoint


def test_parse_datetime_coerces_to_utc():
    parsed = _parse_datetime("2024-01-01T12:00:00")
    assert parsed is not None
    assert parsed.tzinfo == timezone.utc


def test_parse_date_accepts_iso():
    parsed = _parse_date("2024-01-02")
    assert parsed is not None
    assert parsed.isoformat() == "2024-01-02"


def test_row_to_datapoint_maps_fields():
    run_at = datetime(2024, 1, 3, 10, tzinfo=timezone.utc)
    row = (
        "demo",
        "observation",
        "temperature",
        12.5,
        None,
        "C",
        "12.5",
        "C",
        run_at.isoformat(),
        run_at.isoformat(),
        run_at.isoformat(),
        run_at.isoformat(),
        run_at.isoformat(),
        "2024-01-03",
        "hours",
        1,
        "1h",
        0,
        10.0,
        20.0,
        "station-a",
        "source",
        None,
    )
    point = _row_to_datapoint(row)
    assert point.provider == "demo"
    assert point.product_kind == "observation"
    assert point.metric_type == "temperature"
    assert point.run_at == run_at
    assert point.latitude == 10.0
    assert point.longitude == 20.0
