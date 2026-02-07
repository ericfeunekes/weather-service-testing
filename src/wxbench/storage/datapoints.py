"""Data point writer interfaces and helpers."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import sqlite3
from typing import Callable, Iterable, Protocol

from wxbench.domain.models import DataPoint


@dataclass(frozen=True)
class PartitionKey:
    """Partition path and day tag for compaction."""

    path: Path
    day: str


class DataPointWriter(Protocol):
    def write(self, raw_id: int, points: Iterable[DataPoint], *, run_at: datetime) -> int:
        """Write points and return the count stored."""

    def touched_partitions(self) -> tuple[PartitionKey, ...]:
        """Return partition/day pairs touched by this writer."""


DataPointWriterFactory = Callable[[sqlite3.Connection], DataPointWriter]


@dataclass
class CompositeDataPointWriter:
    """Write data points to Parquet first, then to SQLite for overlap."""

    parquet_writer: DataPointWriter
    sqlite_writer: DataPointWriter

    def write(self, raw_id: int, points: Iterable[DataPoint], *, run_at: datetime) -> int:
        buffered = list(points)
        count = self.parquet_writer.write(raw_id, buffered, run_at=run_at)
        self.sqlite_writer.write(raw_id, buffered, run_at=run_at)
        return count

    def touched_partitions(self) -> tuple[PartitionKey, ...]:
        return self.parquet_writer.touched_partitions()
