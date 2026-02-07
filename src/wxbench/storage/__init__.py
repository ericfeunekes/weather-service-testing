"""Storage adapters for persistence.

Adapters in this package translate between domain records and append-only
artifacts such as JSONL snapshots or rendered reports. Keep the boundary thin
so the domain layer can remain unaware of filesystem concerns.
"""

from wxbench.storage.datapoints import (
    CompositeDataPointWriter,
    DataPointWriter,
    DataPointWriterFactory,
    PartitionKey,
)
from wxbench.storage.jsonl import append_records
from wxbench.storage.parquet import (
    ParquetFileRecord,
    ParquetIndexWriter,
    ParquetReadError,
    datapoint_counts_by_run_at as parquet_counts_by_run_at,
    ParquetDataPointWriter,
    compact_partitions,
    resolve_parquet_root,
)
from wxbench.storage.report import ReportArtifacts, generate_daily_report
from wxbench.storage.sqlite import (
    DEFAULT_DB_PATH,
    ParquetIndexRow,
    RawPayload,
    SqliteParquetIndexWriter,
    SqliteDataPointWriter,
    already_ran,
    datapoint_counts_by_run_at as sqlite_counts_by_run_at,
    datapoint_counts_for_runs,
    parquet_counts_for_runs,
    parquet_counts_totals,
    parquet_counts_by_run_at,
    ensure_schema,
    insert_data_points,
    insert_raw_payload,
    open_database,
    prune_data_points_for_runs,
    prune_raw_payloads_for_runs,
    prunable_run_ats,
    upsert_run_history,
    write_parquet_counts,
    run_history_point_counts,
    rebuild_parquet_index,
    list_unsynced_parquet_files,
    record_parquet_sync_results,
)

__all__ = [
    "DEFAULT_DB_PATH",
    "DataPointWriter",
    "DataPointWriterFactory",
    "PartitionKey",
    "RawPayload",
    "SqliteDataPointWriter",
    "CompositeDataPointWriter",
    "ParquetDataPointWriter",
    "ParquetFileRecord",
    "ParquetIndexWriter",
    "ParquetReadError",
    "parquet_counts_by_run_at",
    "compact_partitions",
    "resolve_parquet_root",
    "already_ran",
    "append_records",
    "ReportArtifacts",
    "ensure_schema",
    "generate_daily_report",
    "insert_data_points",
    "insert_raw_payload",
    "open_database",
    "prune_data_points_for_runs",
    "prune_raw_payloads_for_runs",
    "prunable_run_ats",
    "sqlite_counts_by_run_at",
    "parquet_counts_by_run_at",
    "datapoint_counts_for_runs",
    "parquet_counts_for_runs",
    "parquet_counts_totals",
    "run_history_point_counts",
    "upsert_run_history",
    "write_parquet_counts",
    "ParquetIndexRow",
    "SqliteParquetIndexWriter",
    "rebuild_parquet_index",
    "list_unsynced_parquet_files",
    "record_parquet_sync_results",
]
