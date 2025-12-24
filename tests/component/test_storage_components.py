from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path

from wxbench.domain.models import ForecastPeriod, Location, Observation
from wxbench.storage.jsonl import append_records
from wxbench.storage.report import generate_daily_report


def test_append_records_writes_timestamped_jsonl(tmp_path: Path) -> None:
    now = datetime(2023, 5, 2, 12, 0, tzinfo=timezone.utc)

    def fixed_clock() -> datetime:
        return now

    location = Location(latitude=1.0, longitude=2.0)
    records = [
        Observation(
            provider="demo",
            station=None,
            location=location,
            observed_at=datetime(2023, 5, 2, 11, tzinfo=timezone.utc),
            temperature_c=20.5,
        ),
        ForecastPeriod(
            provider="demo",
            location=location,
            issued_at=datetime(2023, 5, 2, 12, tzinfo=timezone.utc),
            start_time=datetime(2023, 5, 2, 12, tzinfo=timezone.utc),
            end_time=datetime(2023, 5, 2, 15, tzinfo=timezone.utc),
            temperature_c=21.0,
        ),
    ]

    path = append_records("demo", records, storage_root=tmp_path, clock=fixed_clock)

    assert path == tmp_path / "2023-05-02" / "demo.jsonl"
    lines = [json.loads(line) for line in path.read_text().splitlines()]
    assert [entry["kind"] for entry in lines] == ["observation", "forecast_period"]
    assert all(entry["stored_at"] == now.isoformat() for entry in lines)
    assert lines[0]["data"]["observed_at"] == "2023-05-02T11:00:00+00:00"
    assert lines[1]["data"]["start_time"] == "2023-05-02T12:00:00+00:00"


def test_generate_daily_report_aggregates_counts(tmp_path: Path) -> None:
    target_day = date(2023, 5, 2)
    location = Location(latitude=10.0, longitude=20.0)
    clock_time = datetime.combine(target_day, datetime.min.time(), tzinfo=timezone.utc)

    def clock() -> datetime:
        return clock_time

    append_records(
        "alpha",
        [
            Observation(
                provider="alpha",
                station="A1",
                location=location,
                observed_at=datetime(2023, 5, 2, 0, tzinfo=timezone.utc),
                temperature_c=18.0,
            ),
            ForecastPeriod(
                provider="alpha",
                location=location,
                issued_at=datetime(2023, 5, 1, 22, tzinfo=timezone.utc),
                start_time=datetime(2023, 5, 2, 0, tzinfo=timezone.utc),
                end_time=datetime(2023, 5, 2, 3, tzinfo=timezone.utc),
                temperature_c=17.5,
            ),
        ],
        storage_root=tmp_path,
        clock=clock,
    )

    append_records(
        "beta",
        [
            ForecastPeriod(
                provider="beta",
                location=location,
                issued_at=datetime(2023, 5, 1, 21, tzinfo=timezone.utc),
                start_time=datetime(2023, 5, 2, 0, tzinfo=timezone.utc),
                end_time=datetime(2023, 5, 2, 6, tzinfo=timezone.utc),
                temperature_c=15.0,
            ),
        ],
        storage_root=tmp_path,
        clock=clock,
    )

    reports_root = tmp_path / "reports"
    artifacts = generate_daily_report(target_day, storage_root=tmp_path, reports_root=reports_root)

    expected = {
        "date": "2023-05-02",
        "providers": {
            "alpha": {"observations": 1, "forecast_periods": 1, "records": 2},
            "beta": {"observations": 0, "forecast_periods": 1, "records": 1},
        },
        "totals": {"observations": 1, "forecast_periods": 2, "records": 3},
    }

    assert artifacts.metrics == expected
    assert artifacts.json_path == reports_root / "2023-05-02.json"
    assert artifacts.markdown_path == reports_root / "2023-05-02.md"

    assert json.loads(artifacts.json_path.read_text()) == expected
    markdown = artifacts.markdown_path.read_text()
    assert "| alpha | 1 | 1 | 2 |" in markdown
    assert "| beta | 0 | 1 | 1 |" in markdown
    assert "| **Total** | **1** | **2** | **3** |" in markdown
