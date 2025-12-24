# README.md

# weather-bench

This repo benchmarks weather forecast accuracy for *your* location.

Minimal viable scope (MVP)
- Ground truth observations: your Ambient Weather station (via AmbientWeather.net API).
- Forecast providers (MVP): OpenWeather + Tomorrow.io.
- Scheduled runs:
  - Hourly: capture one observation snapshot + one forecast snapshot per provider.
  - Daily: score yesterday’s forecasts vs what actually happened and publish a simple report.

Optional later (keep out of MVP unless you need it)
- Environment Canada integration, Apple WeatherKit, AccuWeather, Foreca, Xweather, etc.
- Web dashboard / database / long-term storage.

---

## What you’ll get

1) Raw data you can inspect
- Line-delimited JSON (JSONL) snapshots in `data/`.
- One file per day per source to keep files small and append-friendly.

2) A daily accuracy report
- Markdown summary in `reports/` that ranks providers for:
  - Hourly temperature error (MAE)
  - Daily high/low error (MAE)
  - Precipitation occurrence (simple hit-rate or Brier score)

---

## Setup (phone-friendly)

1) Create a new GitHub repo (private recommended).
2) Add two files to the repo root:
   - `README.md` (this file)
   - `AGENTS.md` (included in this chat)
3) Open Codex Cloud and connect this repo.
4) Tell Codex: “Implement this repo according to README.md and AGENTS.md (start with MVP only).”

When Codex opens a PR, merge it.

Then configure GitHub Actions secrets/vars and wait for the scheduled workflows to run.

---

## Configuration

### GitHub Actions Secrets (required for MVP)
Add these in GitHub → Settings → Secrets and variables → Actions → Secrets:

- `AMBIENT_APPLICATION_KEY`
- `AMBIENT_API_KEY`
- `OPENWEATHER_API_KEY`
- `TOMORROW_API_KEY`

### GitHub Actions Variables (non-secret config)
Add these in GitHub → Settings → Secrets and variables → Actions → Variables:

- `WX_LAT` (e.g., `44.65`)
- `WX_LON` (e.g., `-63.57`)
- `WX_TZ`  (e.g., `America/Halifax`)

Optional:
- `WX_UNITS` (`metric` default)
- `WX_PROVIDER_ENABLE` (comma-separated list, e.g. `ambient,openweather,tomorrow`)

---

## How it runs

GitHub Actions workflows (Codex will create these):
- `.github/workflows/hourly.yml` (cron hourly)
  - Fetch Ambient observation snapshot
  - Fetch forecast snapshots from enabled providers
  - Append to `data/…/*.jsonl`
  - Commit changes back to `main` (or upload artifacts; MVP prefers commit for persistence)

- `.github/workflows/daily.yml` (cron daily)
  - Read yesterday’s raw snapshots
  - Score errors
  - Write `reports/YYYY-MM-DD.md` + a small machine-readable `reports/YYYY-MM-DD.json`
  - Commit the report

---

## Data layout (intended)

data/
  observations/
    ambient/
      2025-01-05.jsonl
  forecasts/
    openweather/
      2025-01-05.jsonl
    tomorrow/
      2025-01-05.jsonl
reports/
  2025-01-05.md
  2025-01-05.json
specs/
  openweather.openapi.json        (if available)
  tomorrow.openapi.json           (if available)
  ambient.openapi.json            (if available; otherwise a short specs/ambient.md)
  README.md                       (notes about how specs were obtained)

---

## Notes / constraints

- You won’t get meaningful rankings until you have at least a few days of data.
- Keep the MVP small: collect snapshots + compute basic scores. Only then add more providers or charts.

---

## Suggested first Codex prompt (copy/paste)

Implement the MVP described in README.md and AGENTS.md:
- Python package + scripts to fetch Ambient obs + OpenWeather + Tomorrow forecasts.
- Store snapshots as JSONL under data/ (one file per day per source).
- Add hourly + daily GitHub Actions workflows.
- Add scoring (MAE for temperature; daily high/low; precip occurrence).
- Tests must run without secrets (use fixtures); add an optional “live smoke test” that runs only if keys exist.
- Add specs/ folder and fetch OpenAPI specs where possible; otherwise write minimal specs/*.md describing endpoints used.

Do not add databases, dashboards, or extra providers in the first PR.
