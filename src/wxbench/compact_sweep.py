"""Compact parquet partitions older than a threshold."""
from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

try:
    import fcntl  # type: ignore[attr-defined]
except ImportError:  # pragma: no cover - platform specific
    fcntl = None

from wxbench.storage.datapoints import PartitionKey
from wxbench.storage.parquet import compact_partitions, resolve_parquet_root
from wxbench.storage.sqlite import SqliteParquetIndexWriter, ensure_schema, open_database


def _acquire_lock(path: Path) -> object | None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = path.open("w")
    if fcntl is None:
        return handle
    try:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        handle.close()
        return None
    return handle


def _collect_partitions(parquet_root: Path, *, age_hours: int | None) -> list[PartitionKey]:
    cutoff = None
    if age_hours is not None:
        cutoff = int(time.time() - age_hours * 3600)
    today_tag = datetime.now(timezone.utc).strftime("%Y%m%d")
    candidates: dict[tuple[Path, str], int] = {}
    for path in parquet_root.rglob("*.parquet"):
        if path.name.startswith(".") or path.name.endswith(".tmp"):
            continue
        if not (path.name.startswith("part-") or path.name.startswith("compact-")):
            continue
        day_tag = None
        for part in path.parts:
            if part.startswith("day="):
                day_tag = part.split("=", 1)[1]
                break
        if day_tag is None and "day=" in path.name:
            day_tag = path.name.split("day=", 1)[1].split("-", 1)[0]
        if day_tag is None or len(day_tag) != 8:
            continue
        if day_tag >= today_tag:
            continue
        key = (path.parent, day_tag)
        mtime = int(path.stat().st_mtime)
        current = candidates.get(key, 0)
        candidates[key] = max(current, mtime)

    partitions: list[PartitionKey] = []
    for (partition, day_tag), mtime in candidates.items():
        if cutoff is not None and mtime > cutoff:
            continue
        partitions.append(PartitionKey(path=partition, day=day_tag))
    return partitions


def run_sweep(
    *,
    data_root: Path,
    db_path: Path,
    age_hours: int | None = None,
    max_bytes: int = 256 * 1024 * 1024,
    acquire_lock: bool = True,
) -> int:
    lock = None
    if acquire_lock:
        lock = _acquire_lock(data_root / "wxbench.lock")
        if lock is None:
            sys.stderr.write("Compaction sweep skipped: lock unavailable\n")
            return 1

    try:
        connection = open_database(db_path)
        ensure_schema(connection)
        parquet_root = resolve_parquet_root(data_root)
        partitions = _collect_partitions(parquet_root, age_hours=age_hours)
        run_id = f"sweep-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
        index_writer = SqliteParquetIndexWriter(connection, parquet_root=parquet_root)
        results = compact_partitions(
            partitions,
            run_id=run_id,
            max_bytes=max_bytes,
            index_writer=index_writer,
            force_single=True,
        )
        connection.commit()
        connection.close()

        failed = sum(1 for result in results if result.status == "failed")
        skipped = sum(1 for result in results if result.status == "skipped")
        success = sum(1 for result in results if result.status == "success")
        sys.stdout.write(
            f"Compaction sweep: success={success} skipped={skipped} failed={failed} partitions={len(results)}\n"
        )
        return 2 if failed else 0
    finally:
        if lock is not None:
            try:
                lock.close()
            except Exception:  # pragma: no cover - defensive
                pass


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compact parquet partitions older than a threshold.")
    parser.add_argument("--data-root", type=Path, default=Path("data"))
    parser.add_argument("--db-path", type=Path, default=None)
    parser.add_argument("--age-hours", type=int, default=None)
    parser.add_argument("--max-bytes", type=int, default=256 * 1024 * 1024)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv or sys.argv[1:])
    db_path = args.db_path or (args.data_root / "wxbench.sqlite")
    return run_sweep(
        data_root=args.data_root,
        db_path=db_path,
        age_hours=args.age_hours,
        max_bytes=args.max_bytes,
    )


if __name__ == "__main__":
    raise SystemExit(main())
