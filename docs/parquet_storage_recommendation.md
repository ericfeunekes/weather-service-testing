# Parquet storage

Normalized data points already write to partitioned Parquet. Keep SQLite for raw payloads, run history, and the Parquet index and sync ledger.

## Current layout

```text
<data-root>/parquet/day=YYYYMMDD/
  part-<run-id>-day=YYYYMMDD-XXXX.parquet
  compact-<run-id>-day=YYYYMMDD.parquet
```

The Parquet writer uses Zstandard compression at level 3. Partitions use the UTC day of `run_at_utc`.

## Operational use

Run the hourly collector to write new Parquet parts. Use the backfill command to export historical SQLite `data_points`.

```bash
python -m wxbench.parquet_backfill --data-root data --db-path data/wxbench.sqlite
wxbench-compact-sweep --data-root data
```

Compaction is separate from the hourly collector. Its default selection excludes the current UTC day. Use the sync command only after compaction when you want complete day files.

```bash
export WX_SYNC_TARGET="<rsync destination>"
wxbench-sync-parquet --data-root data --target "$WX_SYNC_TARGET"
```

The `wxbench-sync-parquet` CLI does not read `WX_SYNC_TARGET`; pass it through the required `--target` argument as shown above. The launchd runner does read `WX_SYNC_TARGET` from its `wxbench.env` file and skips sync explicitly when it is absent.

## Querying

Use a Parquet-capable engine and filter by partition or timestamp before loading rows. For forecast analysis, filter on `valid_start_utc`; use `run_at_utc` to choose forecast vintage. See the [data model and pipeline guide](data_model_and_pipeline.md) for the full timestamp contract.
