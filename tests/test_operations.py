from pathlib import Path
import sqlite3

import pytest

from scripts.backup_database import create_backup
from scripts.healthcheck import check_database, check_disk_space
from scripts.restore_database import restore_backup


def create_source_database(path: Path) -> None:
    connection = sqlite3.connect(path)
    try:
        connection.execute("CREATE TABLE assets (id INTEGER PRIMARY KEY, name TEXT)")
        connection.execute("INSERT INTO assets (name) VALUES ('core-switch')")
        connection.commit()
    finally:
        connection.close()


def test_create_backup_validates_and_retains_newest_files(tmp_path):
    source = tmp_path / "asset_lifecycle.db"
    backup_dir = tmp_path / "backups"
    create_source_database(source)

    first = create_backup(source, backup_dir, retention=1, now="20260716-010000")
    second = create_backup(source, backup_dir, retention=1, now="20260716-020000")

    assert second.exists()
    assert not first.exists()
    connection = sqlite3.connect(second)
    try:
        assert connection.execute("SELECT name FROM assets").fetchone()[0] == "core-switch"
    finally:
        connection.close()


def test_restore_backup_refuses_to_overwrite_an_existing_target(tmp_path):
    source = tmp_path / "asset_lifecycle.db"
    backup_dir = tmp_path / "backups"
    target = tmp_path / "restored.db"
    create_source_database(source)
    backup = create_backup(source, backup_dir, retention=14, now="20260716-010000")
    target.write_bytes(b"existing")

    with pytest.raises(FileExistsError):
        restore_backup(backup, target)


def test_check_database_reports_integrity_failure(tmp_path):
    database = tmp_path / "broken.db"
    database.write_bytes(b"not a sqlite database")

    assert check_database(database).startswith("database integrity check failed:")


def test_check_disk_space_reports_below_threshold(tmp_path, monkeypatch):
    class Usage:
        free = 1024

    monkeypatch.setattr(
        "scripts.healthcheck.shutil.disk_usage", lambda _: Usage()
    )

    assert (
        check_disk_space(tmp_path, minimum_free_bytes=2048)
        == "disk free space below threshold"
    )
