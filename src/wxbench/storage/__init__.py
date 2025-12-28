"""Storage adapters for persistence.

Adapters in this package translate between domain records and append-only
artifacts such as JSONL snapshots or rendered reports. Keep the boundary thin
so the domain layer can remain unaware of filesystem concerns.
"""

from wxbench.storage.jsonl import append_records
from wxbench.storage.report import ReportArtifacts, generate_daily_report
from wxbench.storage.sqlite import (
    DEFAULT_DB_PATH,
    RawPayload,
    ensure_schema,
    insert_data_points,
    insert_raw_payload,
    open_database,
)

__all__ = [
    "DEFAULT_DB_PATH",
    "RawPayload",
    "append_records",
    "ReportArtifacts",
    "ensure_schema",
    "generate_daily_report",
    "insert_data_points",
    "insert_raw_payload",
    "open_database",
]
