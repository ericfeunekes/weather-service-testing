# README.md

# wx-bench

Benchmark weather forecast accuracy for one location using your Ambient weather station as ground truth.

Scope (minimal)
- Collect observations from AmbientWeather.net (your station uploads there).
- Collect forecasts from:
  - OpenWeather (hourly + daily)
  - Tomorrow.io (hourly + daily)
- Run on a schedule:
  - Hourly: capture one observation snapshot + one forecast snapshot per provider.
  - Daily: score yesterday’s data and write a simple report.

Non-goals (keep out of MVP)
- Databases, dashboards, web apps, cloud storage, paid infra.
- Multi-location support.
- Adding every provider at once.

## What this repo will produce

Raw data (append-only, easy to inspect)
- JSONL snapshots stored under `data/`:
  - `data/observations/<source>/YYYY-MM-DD.jsonl`
  - `data/forecasts/<provider>/YYYY-MM-DD.jsonl`

Daily reports
- `reports/YYYY-MM-DD.md` (human-readable ranking + metrics)
- `reports/YYYY-MM-DD.json` (machine-readable metrics)

## Quick start (GitHub Actions)

1) Create a new GitHub repo and add this `README.md` and `AGENTS.md`.
2) Enable GitHub Actions on the repo.
3) Add secrets (GitHub → Settings → Secrets and variables → Actions → Secrets):

- `AMBIENT_APPLICATION_KEY`
- `AMBIENT_API_KEY`
- `OPENWEATHER_API_KEY`
- `TOMORROW_API_KEY`

4) Add variables (GitHub → Settings → Secrets and variables → Actions → Variables):

- `WX_LAT`  (e.g., `44.65`)
- `WX_LON`  (e.g., `-63.57`)
- `WX_TZ`   (e.g., `America/Halifax`)

Optional variables:
- `WX_UNITS` (`metric` default)
- `AMBIENT_DEVICE_MAC` (only if your Ambient account has multiple devices)

After workflows are added, the repo will start collecting snapshots hourly and publishing a daily report.

## Running locally (once implemented)

Create a venv, install dependencies, run fetch + score:

- `python -m venv .venv`
- `source .venv/bin/activate`
- `pip install -r requirements.txt -r requirements-dev.txt`
- `python -m wxbench.fetch`   (or `python scripts/fetch.py`)
- `python -m wxbench.score --date YYYY-MM-DD`

(Exact commands are defined in AGENTS.md and should match the repo.)

## Codex Cloud notes (development)

If you use Codex Cloud to implement or run code in its cloud environment:
- Environment variables persist for the full task.
- “Secrets” are only available to setup scripts and are removed when the agent is running. If you want the agent itself to run live API calls during development/tests, provide keys as environment variables (or rely on fixtures).  [oai_citation:1‡OpenAI Developers](https://developers.openai.com/codex/cloud/environments/)
- Internet access is off by default for the agent phase; enable it only if needed and prefer an allowlist of domains.  [oai_citation:2‡OpenAI Developers](https://developers.openai.com/codex/cloud/internet-access/)

## Repo layout (target)

- `src/wxbench/` (library code)
- `scripts/` (thin wrappers if needed)
- `data/` (raw JSONL snapshots; committed or stored via artifacts, depending on workflow choice)
- `reports/` (daily outputs)
- `specs/` (OpenAPI specs or minimal endpoint docs per provider)
- `.github/workflows/` (hourly + daily schedules
