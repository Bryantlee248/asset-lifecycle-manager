# P0 Operations Assurance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add recoverable SQLite operations, local health monitoring, comprehensive mutation auditing, and restored approval regression coverage without changing HTTPS or public networking.

**Architecture:** Keep operational work outside the FastAPI process. Small Python scripts perform backup, restore-drill, and health checks, while systemd services and timers execute them and retain failures in journald. A focused audit helper serializes safe details to the existing `AuditLog` table, and API mutations call it only after their database change succeeds.

**Tech Stack:** Python 3.12 standard library `sqlite3`, `urllib.request`, `shutil`; FastAPI; SQLAlchemy; pytest; systemd.

---

## File Structure

- Create: `scripts/backup_database.py` - online SQLite backup, validation, and retention.
- Create: `scripts/__init__.py` - make the operations scripts importable in tests and systemd commands.
- Create: `scripts/restore_database.py` - non-destructive restore drill to a new target path.
- Create: `scripts/healthcheck.py` - local API, SQLite, and disk-space checks.
- Create: `backend/audit.py` - credential-safe audit detail serialization and persistence.
- Create: `deploy/systemd/asset-lifecycle-backup.service` - daily backup service.
- Create: `deploy/systemd/asset-lifecycle-backup.timer` - daily backup schedule.
- Create: `deploy/systemd/asset-lifecycle-healthcheck.service` - local health-check service.
- Create: `deploy/systemd/asset-lifecycle-healthcheck.timer` - one-minute health-check schedule.
- Create: `tests/test_operations.py` - backup, restore drill, health check, and audit helper tests.
- Modify: `backend/main.py` - call the audit helper after successful state-changing routes.
- Modify: `backend/approval.py` - use the audit helper for approval actions.
- Modify: `tests/test_approval.py` - replace obsolete `location` fixture arguments.
- Modify: `tests/test_production_mvp.py` - assert approval tests are part of default collection.
- Modify: `tests/test_deployment_templates.py` - verify the new service and timer safeguards.
- Modify: `pytest.ini` - collect the repaired approval suite.
- Modify: `deploy/README.md` - install, operate, restore-test, and troubleshoot P0 units.

### Task 1: Add backup and restore-drill scripts

**Files:**
- Create: `scripts/backup_database.py`
- Create: `scripts/restore_database.py`
- Create: `tests/test_operations.py`

- [ ] **Step 1: Write the failing backup and restore tests**

Create `tests/test_operations.py` with these tests:

```python
from pathlib import Path
import sqlite3

from scripts.backup_database import create_backup
from scripts.restore_database import restore_backup


def create_source_database(path: Path) -> None:
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TABLE assets (id INTEGER PRIMARY KEY, name TEXT)")
        connection.execute("INSERT INTO assets (name) VALUES ('core-switch')")


def test_create_backup_validates_and_retains_newest_files(tmp_path):
    source = tmp_path / "asset_lifecycle.db"
    backup_dir = tmp_path / "backups"
    create_source_database(source)

    first = create_backup(source, backup_dir, retention=1, now="20260716-010000")
    second = create_backup(source, backup_dir, retention=1, now="20260716-020000")

    assert second.exists()
    assert not first.exists()
    with sqlite3.connect(second) as connection:
        assert connection.execute("SELECT name FROM assets").scalar() == "core-switch"


def test_restore_backup_refuses_to_overwrite_an_existing_target(tmp_path):
    source = tmp_path / "asset_lifecycle.db"
    backup_dir = tmp_path / "backups"
    target = tmp_path / "restored.db"
    create_source_database(source)
    backup = create_backup(source, backup_dir, retention=14, now="20260716-010000")
    target.write_bytes(b"existing")

    try:
        restore_backup(backup, target)
    except FileExistsError:
        pass
    else:
        raise AssertionError("restore must not overwrite an existing target")
```

- [ ] **Step 2: Run the tests to verify RED**

Run:

```powershell
python -m pytest tests/test_operations.py -q
```

Expected: collection fails because `scripts.backup_database` and `scripts.restore_database` do not exist.

- [ ] **Step 3: Implement the backup module**

Create `scripts/__init__.py` as an empty file and create `scripts/backup_database.py`:

```python
from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
import sqlite3
import sys


def validate_database(path: Path) -> None:
    with sqlite3.connect(path) as connection:
        result = connection.execute("PRAGMA integrity_check").fetchone()[0]
    if result != "ok":
        raise RuntimeError(f"SQLite integrity check failed: {result}")


def create_backup(source: Path, backup_dir: Path, retention: int, now: str | None = None) -> Path:
    if retention < 1:
        raise ValueError("retention must be at least 1")
    if not source.is_file():
        raise FileNotFoundError(source)
    backup_dir.mkdir(parents=True, exist_ok=True)
    timestamp = now or datetime.now().strftime("%Y%m%d-%H%M%S")
    target = backup_dir / f"asset_lifecycle-{timestamp}.db"
    with sqlite3.connect(source) as source_connection, sqlite3.connect(target) as target_connection:
        source_connection.backup(target_connection)
    validate_database(target)
    backups = sorted(backup_dir.glob("asset_lifecycle-*.db"), key=lambda path: path.name, reverse=True)
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
```

- [ ] **Step 4: Implement the restore-drill module**

Create `scripts/restore_database.py`:

```python
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
    with sqlite3.connect(backup) as source_connection, sqlite3.connect(target) as target_connection:
        source_connection.backup(target_connection)
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
```

- [ ] **Step 5: Run the tests to verify GREEN**

Run:

```powershell
python -m pytest tests/test_operations.py::test_create_backup_validates_and_retains_newest_files tests/test_operations.py::test_restore_backup_refuses_to_overwrite_an_existing_target -q
```

Expected: `2 passed`.

- [ ] **Step 6: Commit the backup scripts**

```powershell
git add scripts tests/test_operations.py
git commit -m "feat: add sqlite backup and restore drill scripts"
```

### Task 2: Add local health-check monitoring

**Files:**
- Create: `scripts/healthcheck.py`
- Modify: `tests/test_operations.py`

- [ ] **Step 1: Write failing health-check tests**

Append to `tests/test_operations.py`:

```python
from scripts.healthcheck import check_database, check_disk_space


def test_check_database_reports_integrity_failure(tmp_path):
    database = tmp_path / "broken.db"
    database.write_bytes(b"not a sqlite database")

    assert check_database(database).startswith("database integrity check failed:")


def test_check_disk_space_reports_below_threshold(tmp_path, monkeypatch):
    class Usage:
        free = 1024

    monkeypatch.setattr("scripts.healthcheck.shutil.disk_usage", lambda _: Usage())

    assert check_disk_space(tmp_path, minimum_free_bytes=2048) == "disk free space below threshold"
```

- [ ] **Step 2: Run the tests to verify RED**

Run:

```powershell
python -m pytest tests/test_operations.py::test_check_database_reports_integrity_failure tests/test_operations.py::test_check_disk_space_reports_below_threshold -q
```

Expected: collection fails because `scripts.healthcheck` does not exist.

- [ ] **Step 3: Implement the health-check module**

Create `scripts/healthcheck.py`:

```python
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
    try:
        with sqlite3.connect(database) as connection:
            result = connection.execute("PRAGMA integrity_check").fetchone()[0]
    except sqlite3.DatabaseError as error:
        return f"database integrity check failed: {error}"
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
```

- [ ] **Step 4: Run the tests to verify GREEN**

Run:

```powershell
python -m pytest tests/test_operations.py -q
```

Expected: all operations-script tests pass.

- [ ] **Step 5: Commit the health check**

```powershell
git add scripts/healthcheck.py tests/test_operations.py
git commit -m "feat: add local operational health check"
```

### Task 3: Add systemd services, timers, and operations documentation

**Files:**
- Create: `deploy/systemd/asset-lifecycle-backup.service`
- Create: `deploy/systemd/asset-lifecycle-backup.timer`
- Create: `deploy/systemd/asset-lifecycle-healthcheck.service`
- Create: `deploy/systemd/asset-lifecycle-healthcheck.timer`
- Modify: `deploy/README.md`
- Modify: `tests/test_deployment_templates.py`

- [ ] **Step 1: Write failing deployment-template tests**

Append to `tests/test_deployment_templates.py`:

```python
def test_backup_timer_uses_the_application_user_and_daily_schedule():
    service = (PROJECT_ROOT / "deploy/systemd/asset-lifecycle-backup.service").read_text(encoding="utf-8")
    timer = (PROJECT_ROOT / "deploy/systemd/asset-lifecycle-backup.timer").read_text(encoding="utf-8")

    assert "User=asset-lifecycle" in service
    assert "scripts.backup_database" in service
    assert "--retention 14" in service
    assert "OnCalendar=*-*-* 02:30:00" in timer


def test_healthcheck_timer_runs_a_local_check_every_minute():
    service = (PROJECT_ROOT / "deploy/systemd/asset-lifecycle-healthcheck.service").read_text(encoding="utf-8")
    timer = (PROJECT_ROOT / "deploy/systemd/asset-lifecycle-healthcheck.timer").read_text(encoding="utf-8")

    assert "scripts.healthcheck" in service
    assert "127.0.0.1:8000/api/health" in service
    assert "--minimum-free-mib 1024" in service
    assert "OnUnitActiveSec=1min" in timer
```

- [ ] **Step 2: Run the tests to verify RED**

Run:

```powershell
python -m pytest tests/test_deployment_templates.py -q
```

Expected: `FileNotFoundError` for the first new unit file.

- [ ] **Step 3: Create the systemd units**

Create `deploy/systemd/asset-lifecycle-backup.service`:

```ini
[Unit]
Description=IT Asset Lifecycle SQLite backup
After=asset-lifecycle.service

[Service]
Type=oneshot
User=asset-lifecycle
Group=asset-lifecycle
WorkingDirectory=/opt/asset-lifecycle-manager
ExecStart=/opt/asset-lifecycle-manager/.venv/bin/python -m scripts.backup_database --database /opt/asset-lifecycle-manager/asset_lifecycle.db --backup-dir /var/backups/asset-lifecycle --retention 14
```

Create `deploy/systemd/asset-lifecycle-backup.timer`:

```ini
[Unit]
Description=Daily IT Asset Lifecycle SQLite backup

[Timer]
OnCalendar=*-*-* 02:30:00
Persistent=true
Unit=asset-lifecycle-backup.service

[Install]
WantedBy=timers.target
```

Create `deploy/systemd/asset-lifecycle-healthcheck.service`:

```ini
[Unit]
Description=IT Asset Lifecycle local health check
After=asset-lifecycle.service

[Service]
Type=oneshot
User=asset-lifecycle
Group=asset-lifecycle
WorkingDirectory=/opt/asset-lifecycle-manager
ExecStart=/opt/asset-lifecycle-manager/.venv/bin/python -m scripts.healthcheck --health-url http://127.0.0.1:8000/api/health --database /opt/asset-lifecycle-manager/asset_lifecycle.db --minimum-free-mib 1024
```

Create `deploy/systemd/asset-lifecycle-healthcheck.timer`:

```ini
[Unit]
Description=Run IT Asset Lifecycle local health check every minute

[Timer]
OnBootSec=1min
OnUnitActiveSec=1min
Unit=asset-lifecycle-healthcheck.service

[Install]
WantedBy=timers.target
```

- [ ] **Step 4: Document host installation and recovery drill**

Append a `## P0 operational tasks` section to `deploy/README.md` containing:

```bash
sudo install -d -o asset-lifecycle -g asset-lifecycle -m 0700 /var/backups/asset-lifecycle
sudo cp deploy/systemd/asset-lifecycle-backup.service deploy/systemd/asset-lifecycle-backup.timer /etc/systemd/system/
sudo cp deploy/systemd/asset-lifecycle-healthcheck.service deploy/systemd/asset-lifecycle-healthcheck.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now asset-lifecycle-backup.timer asset-lifecycle-healthcheck.timer
systemctl list-timers 'asset-lifecycle-*'
sudo systemctl start asset-lifecycle-backup.service
sudo journalctl -u asset-lifecycle-backup.service -n 50 --no-pager
sudo journalctl -u asset-lifecycle-healthcheck.service -n 50 --no-pager
latest=$(sudo find /var/backups/asset-lifecycle -name 'asset_lifecycle-*.db' -type f -printf '%T@ %p\n' | sort -nr | head -1 | cut -d' ' -f2-)
sudo -u asset-lifecycle /opt/asset-lifecycle-manager/.venv/bin/python -m scripts.restore_database --backup "$latest" --target /var/tmp/asset-lifecycle-restore-drill.db
sqlite3 /var/tmp/asset-lifecycle-restore-drill.db 'PRAGMA integrity_check;'
rm /var/tmp/asset-lifecycle-restore-drill.db
```

- [ ] **Step 5: Run the deployment tests to verify GREEN**

Run:

```powershell
python -m pytest tests/test_deployment_templates.py -q
```

Expected: all deployment-template tests pass.

- [ ] **Step 6: Commit the operational deployment assets**

```powershell
git add deploy tests/test_deployment_templates.py
git commit -m "docs: add p0 operational systemd timers"
```

### Task 4: Add centralized credential-safe auditing

**Files:**
- Create: `backend/audit.py`
- Modify: `backend/main.py`
- Modify: `backend/approval.py`
- Modify: `tests/test_operations.py`

- [ ] **Step 1: Write failing audit-helper tests**

Append to `tests/test_operations.py`:

```python
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = PROJECT_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


def test_record_audit_redacts_sensitive_detail_values(isolated_runtime):
    from audit import record_audit
    from database import AuditLog, Base, SessionLocal, engine

    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        record_audit(
            db,
            actor_id=7,
            action="update",
            resource_type="user",
            resource_id="7",
            detail={"password": "secret", "profile": {"token": "abc", "email": "ops@example.com"}},
        )
        db.commit()
        detail = db.query(AuditLog).one().detail
    finally:
        db.close()

    assert "secret" not in detail
    assert "abc" not in detail
    assert "ops@example.com" in detail
```

- [ ] **Step 2: Run the test to verify RED**

Run:

```powershell
python -m pytest tests/test_operations.py::test_record_audit_redacts_sensitive_detail_values -q
```

Expected: collection fails because `audit` does not exist.

- [ ] **Step 3: Implement the audit helper**

Create `backend/audit.py`:

```python
from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session

from database import AuditLog


SENSITIVE_FIELDS = {"password", "password_hash", "token", "jwt", "jwt_secret_key"}


def sanitize_detail(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: "[REDACTED]" if key.lower() in SENSITIVE_FIELDS else sanitize_detail(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [sanitize_detail(item) for item in value]
    return value


def record_audit(
    db: Session,
    actor_id: int,
    action: str,
    resource_type: str,
    resource_id: str,
    detail: dict[str, Any],
) -> AuditLog:
    entry = AuditLog(
        user_id=actor_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        detail=json.dumps(sanitize_detail(detail), ensure_ascii=False, default=str),
    )
    db.add(entry)
    return entry
```

- [ ] **Step 4: Replace direct audit writes and add route coverage**

In `backend/main.py`, import `record_audit` and replace the direct `AuditLog(...)` creation in the asset-delete route. After each mutation is prepared and before its existing final `db.commit()` call for users, roles, assets, procurement, inbound, outbound, changes, faults, warranties, retirements, imports, and approval-template updates, call:

```python
record_audit(
    db,
    current_user.id,
    "create",
    "procurement",
    str(item.id),
    {"after": data.model_dump()},
)
```

Use `"update"` with both `{"before": before, "after": data.model_dump(exclude_unset=True)}` and `"delete"` with `{"before": serialized_item}`. Build `before` and `serialized_item` from explicit model columns; do not serialize SQLAlchemy internals. Call `db.flush()` before auditing a new record so its ID is available, then let the existing final `db.commit()` persist both the record and its audit entry atomically.

In `backend/approval.py`, replace the direct `AuditLog(...)` insertion after approval with:

```python
record_audit(
    db,
    actor_id,
    action,
    "approval_request",
    str(request.id),
    {"asset_code": request.asset_code, "status": request.status, "comment": comment},
)
```

- [ ] **Step 5: Add and run representative route-level audit tests**

Append tests that create an asset through the FastAPI test client and approve a seeded approval request. Assert an `AuditLog` record exists with the expected action, resource type, actor ID, and resource ID. Then run:

```powershell
python -m pytest tests/test_operations.py tests/test_approval.py -q
```

Expected: the audit helper and representative route-level audit tests pass.

- [ ] **Step 6: Commit audit coverage**

```powershell
git add backend/audit.py backend/main.py backend/approval.py tests/test_operations.py
git commit -m "feat: audit critical state changes"
```

### Task 5: Restore approval regression coverage

**Files:**
- Modify: `tests/test_approval.py`
- Modify: `pytest.ini`
- Modify: `tests/test_production_mvp.py`

- [ ] **Step 1: Update approval test fixtures to the current asset schema**

Replace each obsolete asset constructor fragment such as:

```python
Asset(asset_code="SRV-001", lifecycle_stage="运行", location="机房A-01-01")
```

with:

```python
Asset(
    asset_code="SRV-001",
    lifecycle_stage="运行",
    room="机房A",
    cabinet="R-01",
    u_position="U01",
)
```

Give each seeded asset a distinct `room`, `cabinet`, and `u_position` combination. Preserve existing lifecycle stages, asset codes, users, roles, and approval assertions.

- [ ] **Step 2: Run the repaired approval tests to verify the remaining failures**

Run:

```powershell
python -m pytest tests/test_approval.py -q
```

Expected: no constructor error for `location`; address each remaining failure with a focused test and the smallest fixture or production correction justified by that failure.

- [ ] **Step 3: Include approval tests in the default suite**

Update `pytest.ini` to:

```ini
[pytest]
testpaths = tests
python_files =
    test_production_mvp.py
    test_deployment_templates.py
    test_operations.py
    test_approval.py
```

Replace the collection assertion in `tests/test_production_mvp.py` with:

```python
assert "tests/test_approval.py" in result.stdout
assert "tests/functional_test.py" not in result.stdout
```

- [ ] **Step 4: Run the complete local suite**

Run:

```powershell
python -m pytest -q
```

Expected: the release, operations, deployment, and approval suites all pass; `functional_test.py` is not collected.

- [ ] **Step 5: Commit the restored regression suite**

```powershell
git add tests/test_approval.py tests/test_production_mvp.py pytest.ini
git commit -m "test: restore approval regression coverage"
```

### Task 6: Verify source and hand off server activation

**Files:**
- Modify: `deploy/README.md`

- [ ] **Step 1: Run all source verification commands**

Run:

```powershell
python -m pytest -q
python -m compileall backend scripts -q
git diff --check main...HEAD
```

Expected: tests pass, Python compilation exits with status 0, and `git diff --check` reports no whitespace errors.

- [ ] **Step 2: Verify systemd unit syntax on the Linux host**

Run on the deployed server after the source release is installed:

```bash
sudo systemd-analyze verify /etc/systemd/system/asset-lifecycle-backup.service /etc/systemd/system/asset-lifecycle-backup.timer /etc/systemd/system/asset-lifecycle-healthcheck.service /etc/systemd/system/asset-lifecycle-healthcheck.timer
sudo systemctl daemon-reload
sudo systemctl enable --now asset-lifecycle-backup.timer asset-lifecycle-healthcheck.timer
systemctl list-timers 'asset-lifecycle-*'
sudo systemctl start asset-lifecycle-backup.service
sudo systemctl start asset-lifecycle-healthcheck.service
sudo systemctl --failed
```

Expected: both timers are enabled, both manual service runs return success, and no P0 service is listed as failed.

- [ ] **Step 3: Perform a non-production restore drill on the Linux host**

Run:

```bash
latest=$(sudo find /var/backups/asset-lifecycle -name 'asset_lifecycle-*.db' -type f -printf '%T@ %p\n' | sort -nr | head -1 | cut -d' ' -f2-)
sudo -u asset-lifecycle /opt/asset-lifecycle-manager/.venv/bin/python -m scripts.restore_database --backup "$latest" --target /var/tmp/asset-lifecycle-restore-drill.db
sqlite3 /var/tmp/asset-lifecycle-restore-drill.db 'PRAGMA integrity_check;'
rm /var/tmp/asset-lifecycle-restore-drill.db
```

Expected: the temporary restore reports `ok`; the production database path remains unchanged.
