from __future__ import annotations

import argparse
from pathlib import Path
import shutil
import sqlite3
import sys
from urllib.error import URLError
from urllib.request import urlopen


def check_api(url: str, timeout_seconds: int) -> str | None:
    try:
        with urlopen(url, timeout=timeout_seconds) as response:
            if response.status != 200:
                return f"health endpoint returned HTTP {response.status}"
    except URLError as error:
        return f"health endpoint unavailable: {error.reason}"
    return None


def check_database(database: Path) -> str | None:
    connection = None
    try:
        connection = sqlite3.connect(database)
        result = connection.execute("PRAGMA integrity_check").fetchone()[0]
    except sqlite3.DatabaseError as error:
        return f"database integrity check failed: {error}"
    finally:
        if connection is not None:
            connection.close()
    if result != "ok":
        return f"database integrity check failed: {result}"
    return None


def check_disk_space(path: Path, minimum_free_bytes: int) -> str | None:
    if shutil.disk_usage(path).free < minimum_free_bytes:
        return "disk free space below threshold"
    return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--health-url", default="http://127.0.0.1:8000/api/health")
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--minimum-free-mib", type=int, default=1024)
    parser.add_argument("--timeout-seconds", type=int, default=5)
    args = parser.parse_args()

    errors = [
        check_api(args.health_url, args.timeout_seconds),
        check_database(args.database),
        check_disk_space(args.database.parent, args.minimum_free_mib * 1024 * 1024),
    ]
    failures = [error for error in errors if error]
    if failures:
        print("health check failed: " + "; ".join(failures), file=sys.stderr)
        return 1
    print("health check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
