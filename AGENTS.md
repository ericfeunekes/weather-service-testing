# AGENTS.md

## Purpose

This file defines repo-wide engineering constraints for any contributor or coding agent working in this repository.

It is not a task list. Do not add task-specific prompts or one-off instructions here.

## Design rules (hard constraints)

### 1) Pure-core + thin-boundary

- Pure functions live in the domain layer:
  - parsing, validation, normalization
  - mapping provider payloads to internal shapes
  - request building as plain data
  - scoring logic and “what to do next” decisions

- External calls are thin adapters:
  - auth headers, base URLs, timeouts
  - retries/backoff
  - pagination mechanics
  - HTTP client configuration

Everything outside the adapter talks to it through a small interface (protocol or minimal object with a few methods). This seam is mandatory.

### 2) Dependency injection

If logic needs a dependency (HTTP client, clock, UUID, config), inject it as an argument. Do not hide global state in modules.

### 3) Minimal dependencies

Acceptable core libraries (preferred set):
- `httpx` for HTTP
- `tenacity` for retries/backoff
- `vcrpy` for recorded HTTP conversations
- `respx` for systematic HTTP variants/edge cases
- `pydantic` (optional) for response models if it reduces ambiguity

Avoid introducing additional frameworks unless they materially reduce complexity.

## Testing pyramid (repo-wide policy)

Key concept: the recorded HTTP conversation is the reusable artifact.

### Bottom: unit tests (pure functions only)
- Only test pure functions here.
- No network.
- No filesystem dependency unless explicitly part of the pure function contract.
- Fixtures for unit tests live under `tests/fixtures/`.

### Middle: contract + component integration using VCR recordings

1) Contract tests (boundary correctness)
- Record real interactions once using VCR.
- Assert the contract at the boundary:
  - request shape (method, URL/path, query, body schema)
  - key headers (excluding unstable ones)
  - response shape (fields relied on, types, invariants, paging tokens)
  - model round-tripping: raw JSON → response model → internal domain shape

2) Component integration tests (reuse the same cassettes)
- Run real adapter + real mapping + real orchestration logic.
- Use VCR replay to keep tests deterministic and fast.

Policy:
- CI runs in replay-only mode (no new recordings).
- If upstream changes, contract tests should fail loudly and recordings are intentionally re-recorded.

### Expanding coverage without more recordings: respx perturbations
- Use a real cassette response as the baseline “valid” example.
- Use respx to systematically vary edge cases:
  - missing optional fields, nulls, extra fields
  - empty arrays, pagination changes
  - 429/500, timeouts, malformed JSON, slow responses
- Assert retry behavior, error classification, and clear error messages.

### Top: minimal E2E smoke tests
- A small number of live tests against real services.
- Run on a schedule (nightly/weekly) or manually.
- Purpose: detect “world changed” (credentials, rate limits, breaking changes).
- Never gate PRs on live E2E tests.

## Recording rules (VCR)

- All recordings must redact:
  - Authorization headers
  - API keys / tokens in headers or query params
  - any station/device identifiers that should not be public

- Request matching must be tolerant:
  - match on method + URL/path + normalized query/body
  - ignore unstable headers (dates, request IDs, user agents)

- Keep cassettes small and scenario-focused:
  - one cassette per behavior
  - avoid “giant everything” recordings

- Recording modes:
  - Local: allow record/update explicitly (opt-in)
  - CI: replay-only by default; fail on unexpected requests

## Runtime configuration

Read configuration from environment variables only.
- Location: `WX_LAT`, `WX_LON`, `WX_TZ`
- Provider keys: provided via env vars (typically injected from GitHub secrets in workflows)

Never print secrets. Never commit secrets. Never embed secrets in cassettes.

## Error handling expectations

- Adapters must use:
  - explicit timeouts
  - small, bounded retries for transient errors (429/5xx/timeouts) with backoff
- Failures must be classified:
  - auth/config errors vs transient upstream vs parsing/schema errors
- Orchestration must degrade cleanly:
  - if one provider fails, others can still run (unless explicitly configured otherwise)

## Code style

- Small, focused functions.
- Guard clauses over deep nesting.
- Explicit behavior over “magic”.
- Type hints everywhere.
- Side effects isolated at boundaries (HTTP, filesystem, time).

## CI expectations

Default PR pipeline:
- unit tests
- VCR replay-only contract + component tests
- lint/format if configured

Scheduled/manual pipeline:
- minimal live E2E smoke tests (only if required env vars are present)
