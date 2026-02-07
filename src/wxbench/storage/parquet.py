"""Partitioned Parquet storage for normalized data points."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Protocol

import pyarrow as pa
import pyarrow.parquet as pq
import pyarrow.compute as pc

from wxbench.domain.models import DataPoint
from wxbench.storage.datapoints import PartitionKey


DEFAULT_PARQUET_DIRNAME = "parquet"
DEFAULT_COMPRESSION = "zstd"
DEFAULT_COMPRESSION_LEVEL = 3
INDEX_ALL = "__all__"


@dataclass(frozen=True)
class CompactionResult:
    partition: Path
    day: str
    input_files: int
    output_file: Path | None
    output_bytes: int | None
    status: str
    error: str | None = None


@dataclass(frozen=True)
class ParquetFileRecord:
    path: Path
    provider: str
    product_kind: str
    metric_type: str
    day: str
    size_bytes: int
    mtime: int


class ParquetIndexWriter(Protocol):
    def record_files(self, files: Iterable[ParquetFileRecord]) -> None:
        """Record parquet file metadata in an index."""

    def delete_files(self, paths: Iterable[Path]) -> None:
        """Remove parquet file metadata from the index."""


def resolve_parquet_root(data_root: Path) -> Path:
    return data_root / DEFAULT_PARQUET_DIRNAME


def _normalize_datetime(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _day_tag(run_at: datetime) -> str:
    return run_at.strftime("%Y%m%d")


def _day_tag_to_iso(day_tag: str) -> str:
    return f"{day_tag[0:4]}-{day_tag[4:6]}-{day_tag[6:8]}"


def _index_meta() -> tuple[str, str, str]:
    return INDEX_ALL, INDEX_ALL, INDEX_ALL


def _partition_path(
    root: Path,
    *,
    run_at: datetime,
) -> Path:
    day_tag = _day_tag(run_at)
    return root / f"day={day_tag}"


def _schema() -> pa.Schema:
    return pa.schema(
        [
            ("raw_id", pa.int64()),
            ("run_id", pa.string()),
            ("provider", pa.string()),
            ("product_kind", pa.string()),
            ("metric_type", pa.string()),
            ("value_num", pa.float64()),
            ("value_text", pa.string()),
            ("unit", pa.string()),
            ("value_raw", pa.string()),
            ("unit_raw", pa.string()),
            ("observed_at_utc", pa.timestamp("us", tz="UTC")),
            ("valid_start_utc", pa.timestamp("us", tz="UTC")),
            ("valid_end_utc", pa.timestamp("us", tz="UTC")),
            ("issued_at_utc", pa.timestamp("us", tz="UTC")),
            ("run_at_utc", pa.timestamp("us", tz="UTC")),
            ("run_day", pa.date32()),
            ("local_day", pa.date32()),
            ("lead_unit", pa.string()),
            ("lead_offset", pa.int64()),
            ("lead_label", pa.string()),
            ("lead_day_index", pa.int64()),
            ("latitude", pa.float64()),
            ("longitude", pa.float64()),
            ("station", pa.string()),
            ("source_field", pa.string()),
            ("quality_flag", pa.string()),
        ]
    )


class ParquetDataPointWriter:
    """Write data points to partitioned Parquet files."""

    def __init__(
        self,
        root: Path,
        *,
        run_id: str,
        compression: str = DEFAULT_COMPRESSION,
        compression_level: int = DEFAULT_COMPRESSION_LEVEL,
        index_writer: ParquetIndexWriter | None = None,
    ) -> None:
        self._root = root
        self._run_id = run_id
        self._compression = compression
        self._compression_level = compression_level
        self._touched: set[PartitionKey] = set()
        self._counts: dict[tuple[str, str, str, str], int] = {}
        self._counter = 0
        self._wrote_any = False
        self._index_writer = index_writer
        self._index_errors: list[str] = []

    @property
    def wrote_any(self) -> bool:
        return self._wrote_any

    @property
    def index_errors(self) -> tuple[str, ...]:
        return tuple(self._index_errors)

    def write(self, raw_id: int, points: Iterable[DataPoint], *, run_at: datetime) -> int:
        buffered = list(points)
        if not buffered:
            return 0
        run_at = _normalize_datetime(run_at) or datetime.now(timezone.utc)
        day_tag = _day_tag(run_at)
        run_at_value = run_at.isoformat()
        rows_by_partition: dict[Path, list[dict[str, object | None]]] = {}
        partition_meta: dict[Path, tuple[str, str, str]] = {}

        for point in buffered:
            point_run_at = _normalize_datetime(point.run_at)
            if point_run_at is not None and point_run_at != run_at:
                raise ValueError(
                    "DataPoint run_at does not match writer run_at "
                    f"(point={point_run_at.isoformat()} run_at={run_at.isoformat()})"
                )
            partition = _partition_path(
                self._root,
                run_at=run_at,
            )
            rows_by_partition.setdefault(partition, []).append(
                {
                    "raw_id": raw_id,
                    "run_id": self._run_id,
                    "provider": point.provider,
                    "product_kind": point.product_kind,
                    "metric_type": point.metric_type,
                    "value_num": point.value_num,
                    "value_text": point.value_text,
                    "unit": point.unit,
                    "value_raw": point.value_raw,
                    "unit_raw": point.unit_raw,
                    "observed_at_utc": _normalize_datetime(point.observed_at),
                    "valid_start_utc": _normalize_datetime(point.valid_start),
                    "valid_end_utc": _normalize_datetime(point.valid_end),
                    "issued_at_utc": _normalize_datetime(point.issued_at),
                    "run_at_utc": _normalize_datetime(point.run_at) or run_at,
                    "run_day": run_at.date(),
                    "local_day": point.local_day,
                    "lead_unit": point.lead_unit,
                    "lead_offset": point.lead_offset,
                    "lead_label": point.lead_label,
                    "lead_day_index": point.lead_day_index,
                    "latitude": point.latitude,
                    "longitude": point.longitude,
                    "station": point.station,
                    "source_field": point.source_field,
                    "quality_flag": point.quality_flag,
                }
            )
            partition_meta.setdefault(partition, _index_meta())
            key = (point.provider, point.product_kind, point.metric_type, run_at_value)
            self._counts[key] = self._counts.get(key, 0) + 1

        schema = _schema()
        file_records: list[ParquetFileRecord] = []
        for partition, rows in rows_by_partition.items():
            partition.mkdir(parents=True, exist_ok=True)
            self._counter += 1
            file_name = f"part-{self._run_id}-day={day_tag}-{self._counter:04d}.parquet"
            target = partition / file_name
            temp_target = partition / f".{file_name}.tmp"
            table = pa.Table.from_pylist(rows, schema=schema)
            pq.write_table(
                table,
                temp_target,
                compression=self._compression,
                compression_level=self._compression_level,
            )
            temp_target.replace(target)
            self._touched.add(PartitionKey(path=partition, day=day_tag))
            self._wrote_any = True
            meta = partition_meta.get(partition)
            if meta is not None:
                stat = target.stat()
                file_records.append(
                    ParquetFileRecord(
                        path=target,
                        provider=meta[0],
                        product_kind=meta[1],
                        metric_type=meta[2],
                        day=run_at.date().isoformat(),
                        size_bytes=stat.st_size,
                        mtime=int(stat.st_mtime),
                    )
                )

        if self._index_writer is not None and file_records:
            try:
                self._index_writer.record_files(file_records)
            except Exception as exc:  # noqa: BLE001
                self._index_errors.append(f"{exc.__class__.__name__}: {exc}")

        return len(buffered)

    def touched_partitions(self) -> tuple[PartitionKey, ...]:
        return tuple(self._touched)

    def counts(self) -> dict[tuple[str, str, str, str], int]:
        return dict(self._counts)


def compact_partitions(
    partitions: Iterable[PartitionKey],
    *,
    run_id: str,
    max_bytes: int = 256 * 1024 * 1024,
    compression: str = DEFAULT_COMPRESSION,
    compression_level: int = DEFAULT_COMPRESSION_LEVEL,
    index_writer: ParquetIndexWriter | None = None,
    force_single: bool = False,
) -> list[CompactionResult]:
    results: list[CompactionResult] = []
    for partition in partitions:
        result = _compact_partition_day(
            partition.path,
            partition.day,
            run_id=run_id,
            max_bytes=max_bytes,
            compression=compression,
            compression_level=compression_level,
            index_writer=index_writer,
            force_single=force_single,
        )
        results.append(result)
    return results


def _compact_partition_day(
    partition: Path,
    day: str,
    *,
    run_id: str,
    max_bytes: int,
    compression: str,
    compression_level: int,
    index_writer: ParquetIndexWriter | None,
    force_single: bool,
) -> CompactionResult:
    if not partition.exists():
        return CompactionResult(
            partition=partition,
            day=day,
            input_files=0,
            output_file=None,
            output_bytes=None,
            status="skipped",
            error="partition_missing",
        )

    day_token = f"day={day}"
    candidates = []
    for path in sorted(partition.glob("*.parquet")):
        if day_token not in path.name:
            continue
        if not (path.name.startswith("part-") or path.name.startswith("compact-")):
            continue
        try:
            pq.ParquetFile(path)
        except Exception:
            return CompactionResult(
                partition=partition,
                day=day,
                input_files=len(candidates),
                output_file=None,
                output_bytes=None,
                status="failed",
                error=f"metadata_read_failed:{path.name}",
            )
        candidates.append(path)
    if len(candidates) < 2:
        if force_single and len(candidates) == 1:
            single = candidates[0]
            if single.name.startswith("compact-"):
                return CompactionResult(
                    partition=partition,
                    day=day,
                    input_files=1,
                    output_file=single,
                    output_bytes=single.stat().st_size,
                    status="skipped",
                    error="already_compact",
                )
            try:
                table = pq.ParquetFile(single).read()
                table = table.cast(_schema(), safe=False)
            except Exception:
                return CompactionResult(
                    partition=partition,
                    day=day,
                    input_files=1,
                    output_file=None,
                    output_bytes=None,
                    status="failed",
                    error=f"read_failed:{single.name}",
                )
            output_name = f"compact-{run_id}-day={day}.parquet"
            temp_path = partition / f".{output_name}.tmp"
            output_path = partition / output_name
            try:
                pq.write_table(
                    table,
                    temp_path,
                    compression=compression,
                    compression_level=compression_level,
                )
                temp_path.replace(output_path)
            except Exception as exc:  # noqa: BLE001
                return CompactionResult(
                    partition=partition,
                    day=day,
                    input_files=1,
                    output_file=None,
                    output_bytes=None,
                    status="failed",
                    error=f"write_failed:{exc.__class__.__name__}",
                )
            try:
                single.unlink(missing_ok=True)
            except Exception:  # noqa: BLE001
                return CompactionResult(
                    partition=partition,
                    day=day,
                    input_files=1,
                    output_file=output_path,
                    output_bytes=output_path.stat().st_size,
                    status="failed",
                    error="unlink_failed",
                )
            if index_writer is not None:
                stat = output_path.stat()
                record = ParquetFileRecord(
                    path=output_path,
                    provider=INDEX_ALL,
                    product_kind=INDEX_ALL,
                    metric_type=INDEX_ALL,
                    day=_day_tag_to_iso(day),
                    size_bytes=stat.st_size,
                    mtime=int(stat.st_mtime),
                )
                try:
                    index_writer.record_files([record])
                    index_writer.delete_files([single])
                except Exception:  # noqa: BLE001
                    pass
            return CompactionResult(
                partition=partition,
                day=day,
                input_files=1,
                output_file=output_path,
                output_bytes=output_path.stat().st_size,
                status="success",
                error=None,
            )
        return CompactionResult(
            partition=partition,
            day=day,
            input_files=len(candidates),
            output_file=None,
            output_bytes=None,
            status="skipped",
            error="single_file",
        )

    total_bytes = sum(path.stat().st_size for path in candidates)
    if total_bytes > max_bytes:
        return CompactionResult(
            partition=partition,
            day=day,
            input_files=len(candidates),
            output_file=None,
            output_bytes=None,
            status="skipped",
            error="max_bytes_exceeded",
        )

    tables = []
    schema = _schema()
    for path in candidates:
        try:
            table = pq.ParquetFile(path).read()
        except Exception:
            return CompactionResult(
                partition=partition,
                day=day,
                input_files=len(candidates),
                output_file=None,
                output_bytes=None,
                status="failed",
                error=f"read_failed:{path.name}",
            )
        tables.append(table.cast(schema, safe=False))
    if len(tables) < 2:
        return CompactionResult(
            partition=partition,
            day=day,
            input_files=len(candidates),
            output_file=None,
            output_bytes=None,
            status="failed",
            error="insufficient_tables",
        )
    table = pa.concat_tables(tables, promote_options="permissive")

    output_name = f"compact-{run_id}-day={day}.parquet"
    temp_path = partition / f".{output_name}.tmp"
    output_path = partition / output_name

    try:
        pq.write_table(
            table,
            temp_path,
            compression=compression,
            compression_level=compression_level,
        )
        temp_path.replace(output_path)
    except Exception as exc:  # noqa: BLE001
        return CompactionResult(
            partition=partition,
            day=day,
            input_files=len(candidates),
            output_file=None,
            output_bytes=None,
            status="failed",
            error=f"write_failed:{exc.__class__.__name__}",
        )

    for path in candidates:
        if path != output_path:
            try:
                path.unlink(missing_ok=True)
            except Exception:  # noqa: BLE001
                return CompactionResult(
                    partition=partition,
                    day=day,
                    input_files=len(candidates),
                    output_file=output_path,
                    output_bytes=output_path.stat().st_size,
                    status="failed",
                    error="unlink_failed",
                )

    if index_writer is not None:
        stat = output_path.stat()
        record = ParquetFileRecord(
            path=output_path,
            provider=INDEX_ALL,
            product_kind=INDEX_ALL,
            metric_type=INDEX_ALL,
            day=_day_tag_to_iso(day),
            size_bytes=stat.st_size,
            mtime=int(stat.st_mtime),
        )
        try:
            index_writer.record_files([record])
            index_writer.delete_files(candidates)
        except Exception:  # noqa: BLE001
            # Index errors should not invalidate the compaction result.
            pass

    return CompactionResult(
        partition=partition,
        day=day,
        input_files=len(candidates),
        output_file=output_path,
        output_bytes=output_path.stat().st_size,
        status="success",
        error=None,
    )


class ParquetReadError(RuntimeError):
    def __init__(self, path: Path, original: Exception) -> None:
        super().__init__(f"Failed to read parquet file: {path}")
        self.path = path
        self.original = original


def datapoint_counts_by_run_at(parquet_root: Path, run_at: datetime) -> dict[tuple[str, str, str, str], int]:
    if not parquet_root.exists():
        return {}
    run_at = _normalize_datetime(run_at) or datetime.now(timezone.utc)
    day_tag = _day_tag(run_at)
    scalar = pa.scalar(run_at, type=pa.timestamp("us", tz="UTC"))
    columns = ["provider", "product_kind", "metric_type", "run_at_utc"]
    candidates = [path for path in parquet_root.rglob("*.parquet") if f"day={day_tag}" in path.name]
    if not candidates:
        return {}

    counts = {}
    for path in candidates:
        try:
            table = pq.ParquetFile(path).read(columns=columns)
        except Exception as exc:  # noqa: BLE001
            raise ParquetReadError(path, exc) from exc
        filtered = table.filter(pc.equal(table.column("run_at_utc"), scalar))
        if filtered.num_rows == 0:
            continue
        grouped = filtered.group_by(["provider", "product_kind", "metric_type", "run_at_utc"]).aggregate(
            [("run_at_utc", "count")]
        )
        for row in grouped.to_pylist():
            run_at_value = row["run_at_utc"]
            run_at_key = run_at_value.isoformat() if isinstance(run_at_value, datetime) else str(run_at_value)
            key = (row["provider"], row["product_kind"], row["metric_type"], run_at_key)
            counts[key] = counts.get(key, 0) + row["run_at_utc_count"]
    return counts
