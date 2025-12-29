# ADR 0001: Normalize to Data Points + Store Raw Payloads

Date: 2025-12-28
Status: Accepted

## Context

We ingest observations and forecasts from multiple weather providers. Each provider returns different fields,
units, and cadences (current, hourly, daily). We need to compare across providers and preserve as much
signal as possible without forcing a rigid, wide schema that will be mostly NULLs. We also need an audit
trail of what the provider returned to debug mapping issues or failures.

## Decision

1) Store every HTTP response in a raw payloads table.
2) Normalize into a single data-points table where each row is one metric reading.
3) Use canonical units in normalized rows, and retain raw units/values for traceability.
4) Use provider-specific Pydantic models to validate raw payloads based on provider documentation and
   VCR recordings.

### Raw payloads table (one row per HTTP response)

- `raw_payloads`
  - `id` (pk)
  - `provider`
  - `endpoint`
  - `run_at_utc`
  - `request_url`
  - `request_params_json`
  - `request_headers_json` (redacted)
  - `response_status`
  - `response_headers_json` (redacted)
  - `payload_json`
  - `payload_sha256`

### Normalized data points (one row per metric)

- `data_points`
  - `id` (pk)
  - `raw_id` (fk -> `raw_payloads.id`)
  - `provider`
  - `product_kind` (enum-like text: `observation`, `forecast_hourly`, `forecast_daily`)
  - `metric_type` (enum-like text: `temperature_air`, `humidity`, `pressure`, `wind_speed`, etc.)
  - `value_num` (float; nullable if `value_text` is used)
  - `value_text` (string; for non-numeric values like condition text)
  - `unit` (canonical unit: `C`, `kPa`, `kph`, `%`, `mm`, `mm/hr`, `km`, `deg`)
  - `value_raw` (original value, if different)
  - `unit_raw` (original unit, if different)
  - `observed_at_utc` (for observations)
  - `valid_start_utc` (for forecasts)
  - `valid_end_utc` (for forecasts)
  - `issued_at_utc` (provider issue time, if available)
  - `run_at_utc` (cron run time)
  - `local_day` (YYYY-MM-DD for daily forecasts, based on `WX_TZ`)
  - `lead_unit` (`hour` or `day`)
  - `lead_offset` (int, e.g., 5 for `+5h`)
  - `lead_label` (string, e.g., `+5h`, `+3d`)
  - `latitude`
  - `longitude`
  - `station`
  - `source_field` (JSON path used for extraction)
  - `quality_flag` (optional)

## Consequences

- Pros
  - New metrics can be added without schema changes.
  - Comparisons across providers are easier because each metric is standardized.
  - Raw responses are always preserved for debugging and reprocessing.

- Cons
  - Many rows per run; queries need grouping/aggregation.
  - Requires consistent unit normalization across providers.
  - Some provider data may be hard to map into a single metric type.

## Alternatives Considered

- Separate wide tables for observations and forecasts.
  - Rejected due to sparse columns and high schema churn.

- Store only raw payloads.
  - Rejected because cross-provider comparison becomes ad-hoc and expensive.

- Use JSON blobs for normalized data.
  - Rejected because it weakens schema guarantees and queryability.

## Related docs

- `docs/providers/README.md` for provider overview and call matrix.
- `docs/providers/*.md` for provider-specific endpoints, fields, and normalization notes.
