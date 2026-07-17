from __future__ import annotations

import argparse
from pathlib import Path
import sqlite3
import sys

from scripts.backup_database import validate_database


def restore_backup(backup: Path, target: Path) -> Path:
    if not backup.is_file():
        raise FileNotFoundError(backup)
    if target.exists():
        raise FileExistsError(target)

    target.parent.mkdir(parents=True, exist_ok=True)
    source_connection = sqlite3.connect(backup)
    target_connection = sqlite3.connect(target)
    try:
        source_connection.backup(target_connection)
    finally:
        target_connection.close()
        source_connection.close()
    validate_database(target)
    return target


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--backup", type=Path, required=True)
    parser.add_argument("--target", type=Path, required=True)
    args = parser.parse_args()

    try:
        restored = restore_backup(args.backup, args.target)
    except Exception as error:
        print(f"restore drill failed: {error}", file=sys.stderr)
        return 1
    print(f"restore drill created: {restored}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
