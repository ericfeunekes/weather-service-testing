"""Sync parquet files to a remote target using an index + sync ledger."""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Protocol

try:
    import fcntl  # type: ignore[attr-defined]
except ImportError:  # pragma: no cover - platform specific
    fcntl = None

from wxbench.storage.parquet import resolve_parquet_root
from wxbench.storage.sqlite import (
    ParquetIndexRow,
    ensure_schema,
    list_unsynced_parquet_files,
    open_database,
    record_parquet_sync_results,
    rebuild_parquet_index,
)


class SyncTransport(Protocol):
    def sync(self, *, source_root: Path, target: str, paths: list[str]) -> tuple[int, str | None]:
        """Sync file paths from source_root to target."""


class RsyncTransport:
    def __init__(self, rsync_path: str, *, dry_run: bool = False) -> None:
        self._rsync_path = rsync_path
        self._dry_run = dry_run

    def sync(self, *, source_root: Path, target: str, paths: list[str]) -> tuple[int, str | None]:
        if not paths:
            return 0, None
        with tempfile.NamedTemporaryFile("w", delete=False) as handle:
            for path in paths:
                handle.write(f"{path}\n")
            list_path = handle.name
        try:
            cmd = [
                self._rsync_path,
                "-av",
                "--partial",
                "--delay-updates",
                "--dry-run" if self._dry_run else None,
                "--files-from",
                list_path,
                f"{source_root}/",
                target,
            ]
            cmd = [arg for arg in cmd if arg is not None]
            result = subprocess.run(cmd, check=False, capture_output=True, text=True)
            error = result.stderr.strip() if result.returncode != 0 else None
            return result.returncode, error
        finally:
            Path(list_path).unlink(missing_ok=True)


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


def run_sync(
    *,
    data_root: Path,
    db_path: Path,
    target: str,
    age_hours: int | None = None,
    day: str | None = None,
    provider: str | None = None,
    product_kind: str | None = None,
    metric_type: str | None = None,
    path_prefix: str | None = None,
    compacted_only: bool = True,
    dry_run: bool = False,
    transport: SyncTransport | None = None,
) -> int:
    lock = _acquire_lock(data_root / "wxbench.lock")
    if lock is None:
        sys.stderr.write("Sync skipped: lock unavailable\n")
        return 1

    try:
        if transport is None:
            rsync_path = shutil.which("rsync")
            if rsync_path is None:
                sys.stderr.write("Missing dependency: rsync\n")
                return 2
            transport = RsyncTransport(rsync_path, dry_run=dry_run)

        connection = open_database(db_path)
        ensure_schema(connection)
        parquet_root = resolve_parquet_root(data_root)

        min_mtime = None
        if age_hours is not None:
            min_mtime = int(time.time() - age_hours * 3600)

        rows = list_unsynced_parquet_files(
            connection,
            target=target,
            min_mtime=min_mtime,
            day=day,
            provider=provider,
            product_kind=product_kind,
            metric_type=metric_type,
            path_prefix=path_prefix,
            compacted_only=compacted_only,
        )
        if not rows:
            return 0

        paths = [row.path for row in rows]
        code, error = transport.sync(source_root=parquet_root, target=target, paths=paths)
        status = "ok" if code == 0 else "failed"
        if not dry_run:
            record_parquet_sync_results(connection, target=target, rows=rows, status=status, error=error)
            connection.commit()
        connection.close()
        return 0 if code == 0 else 2
    finally:
        try:
            lock.close()
        except Exception:  # pragma: no cover - defensive
            pass


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sync parquet files to a remote target.")
    parser.add_argument("--data-root", type=Path, default=Path("data"))
    parser.add_argument("--db-path", type=Path, default=None)
    parser.add_argument("--target", type=str, default=None)
    parser.add_argument("--age-hours", type=int, default=None)
    parser.add_argument("--day", type=str, default=None)
    parser.add_argument("--provider", type=str, default=None)
    parser.add_argument("--product-kind", type=str, default=None)
    parser.add_argument("--metric-type", type=str, default=None)
    parser.add_argument("--path-prefix", type=str, default=None)
    parser.add_argument("--include-parts", action="store_true", default=False)
    parser.add_argument("--dry-run", action="store_true", default=False)
    parser.add_argument("--rebuild-index", action="store_true", default=False)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv or sys.argv[1:])
    db_path = args.db_path or (args.data_root / "wxbench.sqlite")
    if args.rebuild_index:
        lock = _acquire_lock(args.data_root / "wxbench.lock")
        if lock is None:
            sys.stderr.write("Rebuild skipped: lock unavailable\n")
            return 1
        try:
            connection = open_database(db_path)
            ensure_schema(connection)
            parquet_root = resolve_parquet_root(args.data_root)
            count = rebuild_parquet_index(connection, parquet_root=parquet_root)
            connection.commit()
            connection.close()
            sys.stdout.write(f"Rebuilt parquet index: {count} files\n")
            return 0
        finally:
            try:
                lock.close()
            except Exception:  # pragma: no cover - defensive
                pass

    if not args.target:
        sys.stderr.write("Missing required --target\n")
        return 2

    return run_sync(
        data_root=args.data_root,
        db_path=db_path,
        target=args.target,
        age_hours=args.age_hours,
        day=args.day,
        provider=args.provider,
        product_kind=args.product_kind,
        metric_type=args.metric_type,
        path_prefix=args.path_prefix,
        compacted_only=not args.include_parts,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    raise SystemExit(main())
