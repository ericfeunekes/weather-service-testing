# ADR 0003: Time Zone Comparisons and Lead-Time Semantics

## Status
Accepted

## Context
We compare forecasts from multiple providers against each other and against
observations (Ambient). Providers return data in UTC or with timezone offsets,
but "daily" forecasts are defined in the provider's local day (not UTC day).
If we compare only by UTC day boundaries we mis-align daily values, especially
around time zones and DST shifts.

We also need lead-time labels (e.g., +5h, +3d) to be stable even when a run
occurs a few minutes after the start of a valid hour.

## Decision
1) **Store and compare timestamps in UTC.**
   - All stored `issued_at`, `valid_start`, `valid_end`, and `run_at` values
     are in UTC.
   - Hourly (and sub-hourly) alignment is performed by UTC timestamps.

2) **Daily alignment uses local day derived from the location timezone.**
   - We compute and store `local_day` (YYYY-MM-DD) for daily forecasts.
   - Daily comparisons and scoring use `local_day`, not UTC date.

3) **Lead-time semantics**
   - Hourly lead offsets are computed by hour-bucket alignment:
     `floor_to_hour(start_time_utc) - floor_to_hour(run_at_utc)`.
     This avoids negative offsets when collection happens a few minutes after
     the period starts.
   - Daily lead offsets are the difference between `local_day` values:
     `forecast_local_day - run_local_day`.
   - We also store `lead_day_index` for daily forecasts, defined as the
     provider list order (0-based). This is useful for UI/reporting when a
     provider omits "today" or shifts the start day.

4) **Forecast interval integrity checks**
   - Contract tests enforce monotonic time ordering.
   - Expected steps allow multiples (e.g., 2h gaps in a 1h series), which
     flags disorder or shrinkage but tolerates missing intervals.

## Consequences
- Daily forecasts are compared by `local_day`, preserving provider semantics
  across time zones and DST transitions.
- Hourly forecasts are aligned in UTC, ensuring cross-provider comparison on
  the same valid window.
- Lead offsets are stable and comparable across runs and providers.
- `lead_day_index` preserves provider ordering without replacing `lead_offset`.

## Follow-up considerations
- If we want an index-based daily lead (e.g., "next day" always `+1d`), add a
  separate `lead_day_index` rather than changing the meaning of `lead_offset`.
- If a provider supplies explicit local-day identifiers, we should map them and
  compare against our derived `local_day` for validation.
