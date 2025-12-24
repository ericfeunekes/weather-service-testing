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

## Development setup

Python 3.12+ recommended.

Create and install:
- `python -m venv .venv`
- `source .venv/bin/activate`
- `pip install -r requirements.txt -r requirements-dev.txt`

Run tests:
- `pytest -q`

## How data is stored (intended)

Raw snapshots are append-only JSONL:
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
