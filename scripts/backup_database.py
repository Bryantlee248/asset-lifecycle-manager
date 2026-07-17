from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
import sqlite3
import sys


def validate_database(path: Path) -> None:
    connection = sqlite3.connect(path)
    try:
        result = connection.execute("PRAGMA integrity_check").fetchone()[0]
    finally:
        connection.close()
    if result != "ok":
        raise RuntimeError(f"SQLite integrity check failed: {result}")


def create_backup(
    source: Path, backup_dir: Path, retention: int, now: str | None = None
) -> Path:
    if retention < 1:
        raise ValueError("retention must be at least 1")
    if not source.is_file():
        raise FileNotFoundError(source)

    backup_dir.mkdir(parents=True, exist_ok=True)
    timestamp = now or datetime.now().strftime("%Y%m%d-%H%M%S")
    target = backup_dir / f"asset_lifecycle-{timestamp}.db"
    if target.exists():
        raise FileExistsError(target)

    source_connection = sqlite3.connect(source)
    target_connection = sqlite3.connect(target)
    try:
        source_connection.backup(target_connection)
    finally:
        target_connection.close()
        source_connection.close()
    validate_database(target)

    backups = sorted(
        backup_dir.glob("asset_lifecycle-*.db"),
        key=lambda path: path.name,
        reverse=True,
    )
    for expired in backups[retention:]:
        expired.unlink()
    return target


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--backup-dir", type=Path, required=True)
    parser.add_argument("--retention", type=int, default=14)
    args = parser.parse_args()

    try:
        backup = create_backup(args.database, args.backup_dir, args.retention)
    except Exception as error:
        print(f"backup failed: {error}", file=sys.stderr)
        return 1
    print(f"backup created: {backup}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
