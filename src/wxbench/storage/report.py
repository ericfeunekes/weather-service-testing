"""Daily reporting for stored JSONL records."""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from wxbench.storage.jsonl import DEFAULT_STORAGE_ROOT


@dataclass(frozen=True)
class ReportArtifacts:
    """Paths and metrics generated for a day's report."""

    metrics: dict[str, Any]
    json_path: Path
    markdown_path: Path


def _collect_metrics(day: date, storage_root: Path) -> dict[str, Any]:
    day_dir = storage_root / day.isoformat()
    providers: dict[str, dict[str, int]] = {}
    totals = {"observations": 0, "forecast_periods": 0, "records": 0}

    if not day_dir.exists():
        return {"date": day.isoformat(), "providers": providers, "totals": totals}

    for path in sorted(day_dir.glob("*.jsonl")):
        provider = path.stem
        counts = {"observations": 0, "forecast_periods": 0, "records": 0}
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                counts["records"] += 1
                payload = json.loads(line)
                kind = payload.get("kind")
                if kind == "observation":
                    counts["observations"] += 1
                elif kind == "forecast_period":
                    counts["forecast_periods"] += 1
        providers[provider] = counts
        totals["observations"] += counts["observations"]
        totals["forecast_periods"] += counts["forecast_periods"]
        totals["records"] += counts["records"]

    return {"date": day.isoformat(), "providers": providers, "totals": totals}


def _render_markdown(metrics: dict[str, Any]) -> str:
    lines = [f"# Weather report for {metrics['date']}", "", "| Provider | Observations | Forecast periods | Records |", "|---|---:|---:|---:|"]
    for provider, counts in sorted(metrics["providers"].items()):
        lines.append(
            f"| {provider} | {counts['observations']} | {counts['forecast_periods']} | {counts['records']} |"
        )
    totals = metrics["totals"]
    lines.append(
        f"| **Total** | **{totals['observations']}** | **{totals['forecast_periods']}** | **{totals['records']}** |"
    )
    return "\n".join(lines) + "\n"


def generate_daily_report(
    day: date,
    *,
    storage_root: Path | None = None,
    reports_root: Path | None = None,
) -> ReportArtifacts:
    """Aggregate a day's stored records into JSON and Markdown reports."""

    storage_base = storage_root or DEFAULT_STORAGE_ROOT
    reports_base = reports_root or Path("reports")
    reports_base.mkdir(parents=True, exist_ok=True)

    metrics = _collect_metrics(day, storage_base)
    json_path = reports_base / f"{day.isoformat()}.json"
    markdown_path = reports_base / f"{day.isoformat()}.md"

    json_path.write_text(json.dumps(metrics, indent=2, sort_keys=True), encoding="utf-8")
    markdown_path.write_text(_render_markdown(metrics), encoding="utf-8")

    return ReportArtifacts(metrics=metrics, json_path=json_path, markdown_path=markdown_path)
