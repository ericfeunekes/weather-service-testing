from __future__ import annotations

import os
from pathlib import Path

import httpx
import vcr

from wxbench.config import WxConfig
from wxbench.pipeline import collect_all
from wxbench.storage.sqlite import open_database


CASSETTE_DIR = Path(__file__).parent.parent / "contract" / "cassettes"

recorder = vcr.VCR(
    cassette_library_dir=str(CASSETTE_DIR),
    record_mode=os.getenv("WX_VCR_RECORD_MODE", "none"),
    filter_query_parameters=[
        ("appid", "REDACTED"),
        ("apikey", "REDACTED"),
        ("apiKey", "REDACTED"),
        ("applicationKey", "REDACTED"),
    ],
    filter_headers=["authorization"],
    match_on=["method", "scheme", "host", "port", "path", "query"],
)


def test_collect_all_pipeline_stores_raw_and_points(tmp_path: Path) -> None:
    db_path = tmp_path / "wxbench.sqlite"
    config = WxConfig(
        latitude=45.421,
        longitude=-75.697,
        timezone="America/Toronto",
        provider_keys={
            "WX_OPENWEATHER_API_KEY": os.getenv("WX_OPENWEATHER_API_KEY", "demo"),
            "WX_TOMORROW_IO_API_KEY": os.getenv("WX_TOMORROW_IO_API_KEY", "demo"),
            "WX_ACCUWEATHER_API_KEY": os.getenv("WX_ACCUWEATHER_API_KEY", "demo"),
            "WX_AMBIENT_API_KEY": os.getenv("WX_AMBIENT_API_KEY", "demo"),
            "WX_AMBIENT_APPLICATION_KEY": os.getenv("WX_AMBIENT_APPLICATION_KEY", "demo"),
        },
    )

    with httpx.Client() as client, recorder.use_cassette("pipeline_collect_all.yaml"):
        result = collect_all(config, db_path=db_path, client=client, msc_rdps_max_lead_hours=0)

    assert result.raw_payloads > 0
    assert result.data_points > 0

    connection = open_database(db_path)
    raw_count = connection.execute("SELECT COUNT(*) FROM raw_payloads").fetchone()[0]
    point_count = connection.execute("SELECT COUNT(*) FROM data_points").fetchone()[0]
    metric_types = {
        row[0]
        for row in connection.execute("SELECT DISTINCT metric_type FROM data_points").fetchall()
    }
    connection.close()

    assert raw_count == result.raw_payloads
    assert point_count == result.data_points
    assert "temperature_apparent" in metric_types
    assert "wind_gust" in metric_types
    assert "uv_index" in metric_types
    assert "cloud_cover" in metric_types
