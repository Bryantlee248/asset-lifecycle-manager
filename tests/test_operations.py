from pathlib import Path
import asyncio
import sqlite3
import sys
from types import SimpleNamespace

import pytest

from scripts.backup_database import create_backup
from scripts.healthcheck import check_database, check_disk_space
from scripts.restore_database import restore_backup


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = PROJECT_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


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
            detail={
                "password": "secret",
                "profile": {"token": "abc", "email": "ops@example.com"},
            },
        )
        db.commit()
        detail = db.query(AuditLog).one().detail
    finally:
        db.close()

    assert "secret" not in detail
    assert "abc" not in detail
    assert "ops@example.com" in detail


def test_asset_creation_writes_an_audit_record(isolated_runtime):
    from database import Asset, AuditLog, Base, SessionLocal, User, engine
    from main import create_asset
    from schemas import AssetCreate

    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        actor = User(username="auditor", password_hash="hash", status="active")
        db.add(actor)
        db.commit()
        actor_id = actor.id
        asyncio.run(
            create_asset(
                AssetCreate.model_construct(
                    asset_code="DC-CL-SRV-001", asset_category="服务器"
                ),
                db,
                actor,
            )
        )
        audit = db.query(AuditLog).filter(
            AuditLog.resource_id == "DC-CL-SRV-001"
        ).one()
        asset_count = db.query(Asset).filter(
            Asset.asset_code == "DC-CL-SRV-001"
        ).count()
    finally:
        db.close()

    assert audit.user_id == actor_id
    assert audit.action == "create"
    assert audit.resource_type == "asset"
    assert asset_count == 1


def test_asset_outbound_creation_writes_an_audit_record(isolated_runtime):
    from database import Asset, AuditLog, Base, SessionLocal, User, engine
    from main import create_asset_outbound
    from schemas import OutboundCreate

    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        actor = User(username="outbound-auditor", password_hash="hash", status="active")
        asset = Asset(asset_code="DC-CL-SRV-002", asset_category="server")
        db.add_all([actor, asset])
        db.commit()
        actor_id = actor.id

        asyncio.run(
            create_asset_outbound(
                OutboundCreate.model_construct(
                    asset_code="DC-CL-SRV-002", outbound_category="transfer"
                ),
                db,
                actor,
            )
        )
        audit = db.query(AuditLog).filter(
            AuditLog.resource_type == "asset_outbound"
        ).one()
    finally:
        db.close()

    assert audit.user_id == actor_id
    assert audit.action == "create"


def test_asset_inbound_deletion_writes_one_audit_record(isolated_runtime):
    from database import Asset, AssetInbound, AuditLog, Base, SessionLocal, User, engine
    from main import delete_asset_inbound

    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        actor = User(username="inbound-auditor", password_hash="hash", status="active")
        asset = Asset(asset_code="DC-CL-SRV-004", asset_category="server")
        item = AssetInbound(asset_code="DC-CL-SRV-004")
        db.add_all([actor, asset, item])
        db.commit()
        actor_id = actor.id
        item_id = item.id

        asyncio.run(delete_asset_inbound(item_id, db, actor))
        audits = db.query(AuditLog).filter(
            AuditLog.resource_type == "asset_inbound",
            AuditLog.resource_id == str(item_id),
            AuditLog.action == "delete",
        ).all()
    finally:
        db.close()

    assert len(audits) == 1
    assert audits[0].user_id == actor_id


def test_asset_import_writes_an_audit_record(isolated_runtime, monkeypatch):
    from database import AuditLog, Base, SessionLocal, User, engine
    from main import api_import_assets

    async def import_result(file, db):
        return {"success": 2, "skipped": 0, "errors": [], "total_rows": 2}

    monkeypatch.setattr("main.import_assets_excel", import_result)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        actor = User(username="import-auditor", password_hash="hash", status="active")
        db.add(actor)
        db.commit()
        actor_id = actor.id

        asyncio.run(
            api_import_assets(SimpleNamespace(filename="assets.xlsx"), db, actor)
        )
        audit = db.query(AuditLog).filter(
            AuditLog.resource_type == "import", AuditLog.resource_id == "assets"
        ).one()
    finally:
        db.close()

    assert audit.user_id == actor_id
    assert audit.action == "import"


def test_approval_draft_creation_writes_an_audit_record(isolated_runtime):
    from database import Asset, AuditLog, Base, Role, SessionLocal, User, WorkflowTemplate, engine
    from main import create_approval_request
    from schemas import ApprovalRequestCreate

    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        actor = User(username="request-auditor", password_hash="hash", status="active")
        role = Role(name="Approver", code="approver", permissions="[]")
        asset = Asset(
            asset_code="DC-CL-SRV-003", asset_category="server", lifecycle_stage="planned"
        )
        template = WorkflowTemplate(
            approval_type="test_audit_request",
            approval_type_name="Test audit request",
            current_stage="planned",
            target_stage="purchased",
            mode="single",
            chain=[{"level": 1, "role": "approver"}],
            enabled=True,
        )
        db.add_all([actor, role, asset, template])
        db.commit()

        asyncio.run(
            create_approval_request(
                ApprovalRequestCreate.model_construct(
                    approval_type="test_audit_request",
                    asset_code="DC-CL-SRV-003",
                    reason="Create audit regression request",
                    attachments=[],
                ),
                db,
                actor,
            )
        )
        audit = db.query(AuditLog).filter(
            AuditLog.resource_type == "approval_request"
        ).one()
    finally:
        db.close()

    assert audit.user_id == actor.id
    assert audit.action == "create"


def test_workflow_template_update_writes_an_audit_record(isolated_runtime):
    from database import AuditLog, Base, Role, SessionLocal, User, WorkflowTemplate, engine
    from main import WorkflowTemplateUpdate, update_workflow_template

    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        actor = User(username="template-auditor", password_hash="hash", status="active")
        role = Role(name="Approver", code="approver", permissions="[]")
        template = WorkflowTemplate(
            approval_type="test_audit_template",
            approval_type_name="Test audit template",
            current_stage="planned",
            target_stage="purchased",
            mode="single",
            chain=[{"level": 1, "role": "approver"}],
            enabled=True,
        )
        db.add_all([actor, role, template])
        db.commit()
        actor_id = actor.id

        asyncio.run(
            update_workflow_template(
                template.id,
                WorkflowTemplateUpdate.model_construct(remark="updated by test"),
                db,
                actor,
            )
        )
        audit = db.query(AuditLog).filter(
            AuditLog.resource_type == "approval_template",
            AuditLog.resource_id == str(template.id),
        ).one()
    finally:
        db.close()

    assert audit.user_id == actor_id
    assert audit.action == "update"
