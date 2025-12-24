"""Storage adapters for persistence.

Adapters in this package translate between domain records and append-only
artifacts such as JSONL snapshots or rendered reports. Keep the boundary thin
so the domain layer can remain unaware of filesystem concerns.
"""

from wxbench.storage.jsonl import append_records
from wxbench.storage.report import ReportArtifacts, generate_daily_report

__all__ = ["append_records", "ReportArtifacts", "generate_daily_report"]
