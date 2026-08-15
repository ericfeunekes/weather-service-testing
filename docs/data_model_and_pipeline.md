# Data model and pipeline

Use this guide to interpret collected data, Parquet files, compaction, and sync state.

## Flow

1. `wxbench.runtime` collects provider payloads for one run.
2. It stores raw payloads and normalized `data_points` in SQLite.
3. It writes normalized points to Parquet under the run’s UTC day.
4. `wxbench-compact-sweep` compacts eligible partitions.
5. `wxbench-sync-parquet` syncs indexed, compacted files.

Each run also writes `manifest.json`, `logs.jsonl`, and `metrics.json` under `data/runs/<run_id>/` unless `--data-root` changes the root.

## Storage

SQLite contains `raw_payloads`, `data_points`, `run_history`, `parquet_file_index`, and `parquet_sync`. SQLite retains the audit trail and sync ledger. Parquet provides the analytical copy.

```text
<data-root>/
  wxbench.sqlite
  parquet/
    day=YYYYMMDD/
      part-<run-id>-day=YYYYMMDD-XXXX.parquet
      compact-<run-id>-day=YYYYMMDD.parquet
  runs/<run-id>/
```

Parquet partitions by `run_at_utc`, not forecast validity.

## Timestamp rules

| Field | Meaning |
| --- | --- |
| `run_at_utc` | When wx-bench fetched and normalized the value. |
| `issued_at_utc` | Provider forecast issuance time, when supplied. |
| `observed_at_utc` | Observation time, when applicable. |
| `valid_start_utc` / `valid_end_utc` | Forecast period covered by a value. |
| `local_day` | Local date derived during normalization. |

Filter forecast questions by `valid_start_utc`. Use `run_at_utc` to select a forecast vintage or inspect collection timing.

## Product and unit rules

`product_kind` distinguishes observations from daily, hourly, and minutely forecasts. Compare like products. Aggregate hourly `precip_amount` before comparing it with daily precipitation.

Check `unit` on every query. Snow amount fields are liquid-water equivalent unless the metric explicitly represents depth.

## Compaction and sync

Run compaction separately. It selects partitions older than its age threshold; the default selection excludes the current UTC day.

```bash
wxbench-compact-sweep --data-root data
export WX_SYNC_TARGET="<rsync destination>"
wxbench-sync-parquet --data-root data --target "$WX_SYNC_TARGET"
```

Sync selects only unsynced `compact-*` files unless `--include-parts` is passed. It uses `rsync`, records successful or failed rows in `parquet_sync`, and locks `<data-root>/wxbench.lock` during a run. Use `--dry-run` to inspect a transfer without writing ledger records.

### Unattended sync configuration

The launchd runner reads `WX_SYNC_TARGET` from its existing `wxbench.env` file. It skips sync and logs an explicit message when that variable is absent. Keep it unset until the destination passes non-interactive SSH authorization.

The `wxbench-sync-parquet` CLI remains explicit and requires `--target`; it does not read `WX_SYNC_TARGET` itself.

Use `--rebuild-index` only to rebuild SQLite metadata from existing Parquet files. It does not transfer files.
