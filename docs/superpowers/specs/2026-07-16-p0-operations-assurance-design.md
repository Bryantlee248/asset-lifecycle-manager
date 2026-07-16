# P0 Operations Assurance Design

## Goal

Make the single-server deployment operationally recoverable and observable without
adding HTTPS or an external alerting service.

## Scope

- Create a daily SQLite backup and retain the newest 14 backups.
- Verify every backup without modifying the production database.
- Run a local system health check every minute.
- Write failures to the systemd journal so the host can surface failed units.
- Record critical state-changing API operations through one audit helper.
- Restore approval regression tests to the default pytest suite.

## Non-Goals

- HTTPS, domains, or public-port changes.
- Email, SMS, WeCom, DingTalk, or other external notifications.
- Automatic restoration over the production database.
- Database migration from SQLite to PostgreSQL.

## Components

### Backup

`scripts/backup_database.py` will accept the database path, backup directory, and
retention count as command-line arguments. It will use SQLite's online backup API,
run `PRAGMA integrity_check` against the generated backup, and delete only backups
older than the configured retention count. It will return a nonzero exit code on
failure and write a concise error to stderr for journald.

`deploy/systemd/asset-lifecycle-backup.service` runs the script as the application
user. `asset-lifecycle-backup.timer` schedules it once per day. The service never
overwrites the source database.

### Local Health Check

`scripts/healthcheck.py` will check the local `/api/health` endpoint, run SQLite
`PRAGMA integrity_check`, and reject a filesystem with less than the configured
free-space threshold. Any failed check returns a nonzero exit code and includes the
failed condition in stderr.

`deploy/systemd/asset-lifecycle-healthcheck.service` runs the check as the
application user. `asset-lifecycle-healthcheck.timer` runs it once per minute. The
host operator can inspect failures with `systemctl --failed` and `journalctl -u
asset-lifecycle-healthcheck.service`.

### Audit Trail

`backend/audit.py` will expose a narrow helper that receives the database session,
actor ID, action, resource type, resource ID, and a JSON-safe detail object. It will
remove password, password hash, token, and JWT-secret fields before persisting the
detail in `AuditLog`.

The existing CRUD and approval handlers will call this helper after successful
changes. Coverage includes users, roles, assets, procurement, inbound and outbound
records, changes, faults, warranties, retirements, imports, approval actions, and
approval-template updates. Read-only requests are not audited.

### Regression Tests

`tests/test_approval.py` will be updated to build assets with the current
`room`, `cabinet`, and `u_position` fields instead of the removed `location` field.
The default pytest configuration will include the approval suite after it passes.

New focused tests will cover backup creation, retention, backup verification,
health-check failures, audit redaction, and representative audit records from a
CRUD change and an approval action.

## Deployment

The deployment guide will document installation of the two service/timer pairs,
creation of `/var/backups/asset-lifecycle`, journal inspection, backup restoration
into a separate target path, and timer status checks. The source change does not
log into or alter the currently deployed cloud host; applying the templates requires
the server-management step after source verification.

## Acceptance Criteria

1. A backup timer creates a valid backup and retains only the newest 14 files.
2. A corrupt backup or unavailable database makes the relevant service fail and
   writes an actionable journal error.
3. The health timer detects API, SQLite, and low-disk failures without changing
   production data.
4. Sensitive credential fields never appear in audit details.
5. Representative CRUD and approval mutations create audit records.
6. `python -m pytest -q` includes and passes the restored approval tests plus the
   P0 operations tests.
