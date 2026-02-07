from __future__ import annotations

from datetime import datetime, timedelta, timezone

from wxbench.compact_sweep import _collect_partitions


def test_collect_partitions_excludes_today(tmp_path):
    parquet_root = tmp_path / "parquet"
    today_tag = datetime.now(timezone.utc).strftime("%Y%m%d")
    yesterday_tag = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y%m%d")

    for day_tag in (today_tag, yesterday_tag):
        day_dir = parquet_root / f"day={day_tag}"
        day_dir.mkdir(parents=True, exist_ok=True)
        (day_dir / f"part-test-day={day_tag}-0001.parquet").write_text("x")

    partitions = _collect_partitions(parquet_root, age_hours=None)
    days = {partition.day for partition in partitions}

    assert yesterday_tag in days
    assert today_tag not in days
