# wx-bench

Collect normalized weather observations and forecasts for one configured location. Compare provider output against station data without using live services in CI.

## Start here

Use Python 3.12 or later.

```bash
uv venv
source .venv/bin/activate
uv pip install -e ".[dev]"
pytest -q
```

Set location values and only the provider credentials you use. Copy [configs/env.example](configs/env.example) into a local, ignored environment file if that suits your workflow.

```bash
export WX_LAT="<latitude>"
export WX_LON="<longitude>"
export WX_TZ="<IANA timezone>"
```

Run one collection cycle. It writes SQLite, Parquet, and per-run artifacts under `data/` by default.

```bash
python -m wxbench.runtime --msc-rdps-max-lead-hours 24
```

Use `--data-root` to move run artifacts and the default database. Use `--db-path` to choose a database separately.

## What is implemented

- Provider adapters for AccuWeather, Ambient Weather, Ecowitt, MSC GeoMet, MSC RDPS PROGNOS, OpenWeather, Tomorrow.io, and WeatherKit.
- Normalized observations and forecast periods persisted as SQLite `data_points` and partitioned Parquet.
- Per-run manifest, log, and metrics files under `data/runs/<run_id>/`.
- Parquet backfill, compaction, indexed sync, and a Google Routes plus WeatherKit trip-brief CLI.

Missing credentials skip only their provider during the hourly run. MSC GeoMet and MSC RDPS PROGNOS do not require credentials.

## Storage and sync

Parquet lives at `<data-root>/parquet/`; the default is `data/parquet/`. Compact previous UTC-day partitions before syncing them:

```bash
wxbench-compact-sweep --data-root data
export WX_SYNC_TARGET="<rsync destination>"
wxbench-sync-parquet --data-root data --target "$WX_SYNC_TARGET"
```

The sync command transfers only `compact-*` files by default and records completed transfers in SQLite. The CLI requires `--target`. The launchd runner reads `WX_SYNC_TARGET` from `wxbench.env` and skips sync explicitly when it is absent. See the [data model and pipeline guide](docs/data_model_and_pipeline.md) for the operational boundary.

## Documentation

- [Provider contract references](docs/provider_contracts.md)
- [Data model and pipeline](docs/data_model_and_pipeline.md)
- [Provider products and metrics](docs/provider_products_and_metrics.md)
- [Trip brief CLI](docs/trip_brief_cli.md)
- [Parquet storage](docs/parquet_storage_recommendation.md)

## Tests and recordings

```bash
pytest -q
WX_VCR_RECORD_MODE=all pytest tests/contract -q
```

The first command replays recordings and must not use the network. The second command intentionally records or refreshes contracts, so export only the required credentials first. Recordings redact secrets; never commit credentials or precise personal-location details.

## Repository layout

- `src/wxbench/domain/`: pure models and provider mappings.
- `src/wxbench/providers/`: HTTP adapters, retries, and capture.
- `src/wxbench/storage/`: SQLite, Parquet, JSONL, and reports.
- `tests/`: unit, contract, and component coverage.

See [AGENTS.md](AGENTS.md) for the architecture, dependency-injection, and test-boundary rules.
