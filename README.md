# README.md

# wx-bench

Benchmarks weather forecast accuracy for a single configured location, using your own weather station as ground truth.

This repo is designed to be automation-first (GitHub Actions) and testable without relying on live external services in CI.

## Repo-wide principles

Architecture
- Keep business logic pure where possible.
- Treat external HTTP calls as a thin adapter behind a hard seam.
- Pass dependencies (client, clock, config) as arguments so orchestration remains testable.

Testing
- Recorded HTTP conversations are reusable artifacts.
- CI must be deterministic: replay recordings, do not hit the network.
- Live end-to-end checks are smoke tests only and run on a schedule or manually.

## Repository layout (target)

- `src/wxbench/`
  - `domain/` pure logic: mapping, validation, scoring, decisions
  - `providers/` boundary adapters: HTTP calls, auth, retries, timeouts
  - `storage/` append-only JSONL and report writers
- `tests/`
  - `unit/` pure-function tests only
  - `contract/` VCR-based boundary contract tests (replay in CI)
  - `component/` larger slices using the same cassettes (replay in CI)
  - `e2e/` minimal live smoke tests (not run on PRs)
  - `fixtures/` golden JSON used by unit tests and respx variants
  - `cassettes/` VCR recordings (redacted)
- `data/` (optional, depending on workflow persistence choice)
- `reports/` daily outputs
- `specs/` OpenAPI specs (if available) or minimal endpoint docs

## Configuration

All runtime configuration is via environment variables.

Location
- `WX_LAT`
- `WX_LON`
- `WX_TZ` (IANA timezone)

Provider keys are expected via environment variables at runtime (in GitHub Actions these come from repo secrets). Do not commit keys.

## Hourly runtime (recommended)

The scheduled runner ensures a single hourly run, skips if the current hour already exists, and writes per-run artifacts:

```
python -m wxbench.runtime --msc-rdps-max-lead-hours 24
```

Artifacts are written under `data/runs/<run_id>/`:

- `manifest.json` – run parameters, counts, errors, and outputs
- `logs.jsonl` – start/finish/skip plus per-provider start/success/error events (JSONL)
- `metrics.json` – compact per-run metrics

The runner defaults to `max_lead_hours=24` for RDPS PROGNOS to keep hourly runs lightweight; override the flag if you want the full 0–84 range.

To store artifacts in Application Support, pass a data root and (optionally) an explicit DB path:

```
python -m wxbench.runtime --data-root "$HOME/Library/Application Support/wxbench" --db-path "$HOME/Library/Application Support/wxbench/wxbench.sqlite"
```

### Runbook (minimal)

- Rerun safely: re-run the hourly command; it will skip if the hour already exists.
- Backfill: true backfills aren’t supported by most provider endpoints; reruns will capture “latest” data only.
- Inspect state: query `data/wxbench.sqlite` (`raw_payloads`, `data_points`) and review `data/runs/<run_id>/manifest.json`.
- Outputs: raw payloads and normalized points are stored in SQLite; run artifacts are in `data/runs/<run_id>/`.
- Rollback: delete the specific hour’s rows from SQLite using `run_at_utc` bounds if you need to invalidate a run.

## Development setup

Python 3.12+ recommended.

Create and install:
- `uv venv`
- `source .venv/bin/activate`
- `uv pip install -e ".[dev]"`

Run tests:
- `pytest -q`

### Recording or refreshing contract tests

Contract tests use VCR cassettes by default. To exercise the live provider APIs and regenerate recordings:

1. Export API keys (only required for authenticated providers):
   - `WX_OPENWEATHER_API_KEY` – OpenWeather
   - `WX_ACCUWEATHER_API_KEY` – AccuWeather MinuteCast
   - `WX_TOMORROW_IO_API_KEY` – Tomorrow.io
   - `WX_AMBIENT_API_KEY` and `WX_AMBIENT_APPLICATION_KEY` – Ambient Weather
   - Optional location override for contract tests: `WX_LAT` and `WX_LON`.
   - Trailing whitespace in environment variables is stripped automatically to avoid hidden newline issues during live runs.
2. Enable recording: `WX_VCR_RECORD_MODE=all pytest tests/contract -q`

Cassettes redact API keys automatically; never commit raw credentials.

### Live provider connectivity (latest run)

Command: `WX_VCR_RECORD_MODE=all pytest tests/contract -rs -q`

Required environment for a full live run (all providers):

- `WX_AMBIENT_API_KEY` and `WX_AMBIENT_APPLICATION_KEY`
- `WX_ACCUWEATHER_API_KEY`
- `WX_OPENWEATHER_API_KEY`
- `WX_TOMORROW_IO_API_KEY`
- Optional location override: `WX_LAT` and `WX_LON`

Latest recorded attempt (2025-12-28):

- ✅ MSC GeoMet forecast and observation calls hit the live `citypageweather-realtime` endpoint without credentials using the
  default Ottawa bounding box (uses `WX_LAT/WX_LON` if set).
- ✅ OpenWeather forecast and observation calls succeeded against live endpoints with the provided `WX_OPENWEATHER_API_KEY`.
- ✅ Tomorrow.io forecast and observation calls succeeded against live endpoints with the provided `WX_TOMORROW_IO_API_KEY`.
- ✅ Ambient Weather observation calls succeeded once both `WX_AMBIENT_API_KEY` and `WX_AMBIENT_APPLICATION_KEY` were present.

Re-run the command above after exporting the missing keys (and optional `*_LAT/LON` overrides) to exercise the live APIs and
refresh the VCR cassettes.

## Refreshing provider specs

OpenAPI documents for unauthenticated providers can be downloaded locally with
httpx. The helper script saves each document to `specs/{provider}.json` without
any redaction or API keys. The default target is Environment and Climate Change
Canada's MSC GeoMet OGC API (`https://api.weather.gc.ca/openapi`), which is
public and does not require authentication.

```
PYTHONPATH=src python scripts/fetch_specs.py
```

The command relies only on public documentation endpoints and can be run from
any development environment.

## How data is stored (intended)

SQLite (preferred):
- `data/wxbench.sqlite`
- `raw_payloads` stores each HTTP response (redacted metadata + raw payload).
- `data_points` stores normalized per-metric rows for observations + forecasts.

Legacy/optional JSONL:
- One file per day per source/provider.
- Each line is one “snapshot event” with a capture timestamp and raw provider payload.

Daily reports:
- `reports/YYYY-MM-DD.md` (human-readable)
- `reports/YYYY-MM-DD.json` (machine-readable metrics)

## CI expectations

- Unit tests: no network, no external files required.
- Contract/component tests: VCR replay-only in CI.
- E2E smoke: scheduled or manual, not on every PR.

## Security and privacy

- Never log secrets.
- VCR recordings must redact auth headers, tokens, and any sensitive identifiers.
- Avoid embedding precise personal location details in documentation. Use only configuration variables.

## Contributing

See `AGENTS.md` for repo-wide engineering rules (testing pyramid, seams, recording policy, and library choices).
