"""审批工作流模块单元测试 - P0/P1/P2 全覆盖
使用 pytest 框架，SQLite 内存数据库 + ORM 直接调用核心引擎函数
"""
import sys
import os
import json
from datetime import datetime, timezone, date
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine, func
from sqlalchemy.orm import sessionmaker, DeclarativeBase

# ============ 路径设置：将 backend 目录加入 sys.path ============
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKEND_DIR = os.path.join(PROJECT_ROOT, "backend")
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

# ============ 构建内存数据库 Base 和表 ============
# 为避免修改原始 database.py 中的全局 engine，我们在测试中
# 使用独立的内存数据库引擎和 Base 类
from database import (ApprovalRequest, ApprovalStep, ApprovalNotification,
                      Asset, User, Role, AuditLog, user_roles, WorkflowTemplate)
from validation import check_stage_gate
from approval import (generate_request_no, auto_assign_approver,
                      create_approval_steps, create_notification,
                      notify_approver, notify_applicant,
                      submit_approval, process_approval_action,
                      drive_stage_change, cancel_approval,
                      resubmit_approval)
from config_cache import build_stage_gate_cache
from seed_stage_transitions import seed_stage_transitions
from seed_workflow_templates import seed_workflow_templates
from constants import (APPROVAL_TYPE_NAMES,
                       APPROVAL_TYPE_FAULT_DEGRADE, APPROVAL_TYPE_MIGRATION,
                       APPROVAL_TYPE_RETIREMENT, APPROVAL_TYPE_PROCUREMENT,
                       APPROVAL_TYPE_INSPECTION, APPROVAL_TYPE_WARRANTY_RENEWAL,
                       APPROVAL_STATUS_DRAFT, APPROVAL_STATUS_PENDING,
                       APPROVAL_STATUS_APPROVED, APPROVAL_STATUS_REJECTED,
                       APPROVAL_STATUS_CANCELLED,
                       APPROVAL_STEP_PENDING, APPROVAL_STEP_APPROVED,
                       APPROVAL_STEP_REJECTED)

# 使用内存数据库引擎（每个测试函数独立创建）
_test_engine = None
_TestSessionLocal = None


def _create_memory_db():
    """创建内存数据库引擎和会话工厂，建表后返回"""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    # 将所有模型绑定到此内存引擎
    from database import Base
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return engine, SessionLocal


# ============ Fixture: 提供独立的内存数据库会话 ============

@pytest.fixture
def db_session():
    """为每个测试提供独立的内存数据库会话，测试结束后回滚"""
    engine, SessionLocal = _create_memory_db()
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def seeded_db(db_session):
    """预填充基础数据（角色、用户、资产）的数据库会话"""
    db = db_session
    # 创建角色
    admin_role = Role(name="系统管理员", code="admin", permissions=json.dumps(["approval:view", "approval:submit", "approval:approve", "approval:cancel"]), is_system=True)
    ops_mgr_role = Role(name="运维主管", code="ops_manager", permissions=json.dumps(["approval:view", "approval:submit", "approval:approve", "approval:cancel"]), is_system=True)
    ops_eng_role = Role(name="运维工程师", code="ops_engineer", permissions=json.dumps(["approval:view", "approval:submit"]), is_system=True)
    viewer_role = Role(name="只读用户", code="viewer", permissions=json.dumps(["approval:view"]), is_system=True)
    db.add_all([admin_role, ops_mgr_role, ops_eng_role, viewer_role])
    db.flush()

    # 创建用户
    admin_user = User(username="admin", password_hash="hashed_admin123", real_name="管理员", status="active")
    ops_mgr_user = User(username="ops_mgr", password_hash="hashed_ops_mgr", real_name="运维主管", status="active")
    ops_eng_user = User(username="ops_eng", password_hash="hashed_ops_eng", real_name="运维工程师", status="active")
    viewer_user = User(username="viewer_user", password_hash="hashed_viewer", real_name="只读用户", status="active")
    disabled_user = User(username="disabled_mgr", password_hash="hashed_disabled", real_name="已禁用运维主管", status="disabled")
    db.add_all([admin_user, ops_mgr_user, ops_eng_user, viewer_user, disabled_user])
    db.flush()

    # 关联角色
    admin_user.roles.append(admin_role)
    ops_mgr_user.roles.append(ops_mgr_role)
    ops_eng_user.roles.append(ops_eng_role)
    viewer_user.roles.append(viewer_role)
    disabled_user.roles.append(ops_mgr_role)
    db.flush()

    # 创建资产（不同阶段）
    asset_running = Asset(asset_code="SRV-001", asset_category="服务器", brand="Dell", model="R740",
                          lifecycle_stage="运行", room="机房A", cabinet="R-01", u_position="1U", responsible_person="张三",
                          warranty_status="在保", warranty_expire_date=date(2027, 1, 1))
    asset_repair = Asset(asset_code="SRV-002", asset_category="服务器", brand="HP", model="DL380",
                         lifecycle_stage="维修", room="机房B", cabinet="R-02", u_position="2U", responsible_person="李四",
                         warranty_status="过保", warranty_expire_date=date(2024, 6, 1))
    asset_planning = Asset(asset_code="SRV-003", asset_category="服务器", brand="Lenovo", model="SR650",
                          lifecycle_stage="规划", responsible_person="王五",
                          warranty_status="无维保")
    asset_transit = Asset(asset_code="SRV-004", asset_category="服务器", brand="Inspur", model="NF5280",
                          lifecycle_stage="在途", room="仓库", responsible_person="赵六",
                         warranty_status="无维保")
    asset_installed = Asset(asset_code="SRV-005", asset_category="服务器", brand="Huawei", model="2280",
                            lifecycle_stage="上架", room="机房C", cabinet="R-03", u_position="3U", responsible_person="钱七",
                           warranty_status="在保", warranty_expire_date=date(2028, 12, 1))
    asset_pending_retire = Asset(asset_code="SRV-006", asset_category="服务器", brand="Dell", model="R720",
                                 lifecycle_stage="待报废", room="机房A", cabinet="R-01", u_position="2U", responsible_person="孙八",
                                 warranty_status="过保")
    db.add_all([asset_running, asset_repair, asset_planning, asset_transit, asset_installed, asset_pending_retire])
    db.commit()
    seed_workflow_templates(db)
    seed_stage_transitions(db)
    build_stage_gate_cache(db)

    return db


def _create_approval_request(db, approval_type, asset_code, current_stage, target_stage,
                              reason="测试审批原因", applicant_id=1):
    """辅助函数：创建一个 draft 状态的审批单"""
    request_no = generate_request_no(db)
    request = ApprovalRequest(
        request_no=request_no,
        approval_type=approval_type,
        asset_code=asset_code,
        current_stage=current_stage,
        target_stage=target_stage,
        reason=reason,
        attachments="[]",
        status=APPROVAL_STATUS_DRAFT,
        applicant_id=applicant_id,
    )
    db.add(request)
    db.flush()
    return request


# ========================================================
# P0 - 核心引擎逻辑
# ========================================================

class TestGenerateRequestNo:
    """测试 generate_request_no() 单号生成格式 APR-YYYYMMDD-SEQ"""

    def test_first_request_of_day(self, seeded_db):
        """当日首个审批单号应为 APR-YYYYMMDD-001"""
        db = seeded_db
        request_no = generate_request_no(db)
        today_str = datetime.now(timezone.utc).strftime("%Y%m%d")
        assert request_no == f"APR-{today_str}-001"

    def test_second_request_of_day(self, seeded_db):
        """当日第二个审批单号递增为 APR-YYYYMMDD-002"""
        db = seeded_db
        # 先创建一个已有审批单
        _create_approval_request(db, APPROVAL_TYPE_FAULT_DEGRADE, "SRV-001", "运行", "维修")
        # 第二次调用
        request_no = generate_request_no(db)
        today_str = datetime.now(timezone.utc).strftime("%Y%m%d")
        assert request_no == f"APR-{today_str}-002"

    def test_multi_requests_same_day(self, seeded_db):
        """同日多单号连续递增"""
        db = seeded_db
        nos = []
        for i in range(5):
            req = _create_approval_request(db, APPROVAL_TYPE_FAULT_DEGRADE, "SRV-001", "运行", "维修",
                                           reason=f"测试单号{i+1}")
            nos.append(req.request_no)
        today_str = datetime.now(timezone.utc).strftime("%Y%m%d")
        # 验证序号从001到005递增
        for i, no in enumerate(nos, 1):
            expected = f"APR-{today_str}-{i:03d}"
            assert no == expected, f"第{i}个单号应为{expected}，实际为{no}"

    def test_format_structure(self, seeded_db):
        """单号格式结构验证：APR-前缀 + 8位日期 + 3位序号"""
        db = seeded_db
        request_no = generate_request_no(db)
        parts = request_no.split("-")
        assert parts[0] == "APR"
        assert len(parts[1]) == 8  # YYYYMMDD
        assert len(parts[2]) == 3  # SEQ
        # 验证日期部分为数字
        assert parts[1].isdigit()
        # 验证序号部分为数字
        assert parts[2].isdigit()


class TestAutoAssignApprover:
    """测试 auto_assign_approver() 根据角色编码自动指派审批人"""

    def test_assign_ops_manager(self, seeded_db):
        """ops_manager角色应指派该角色下第一个活跃用户"""
        db = seeded_db
        approver = auto_assign_approver(db, "ops_manager")
        assert approver is not None
        assert approver.status == "active"
        # 验证该用户具有ops_manager角色
        role_codes = [r.code for r in approver.roles]
        assert "ops_manager" in role_codes

    def test_assign_admin(self, seeded_db):
        """admin角色应指派该角色下第一个活跃用户"""
        db = seeded_db
        approver = auto_assign_approver(db, "admin")
        assert approver is not None
        assert approver.status == "active"
        role_codes = [r.code for r in approver.roles]
        assert "admin" in role_codes

    def test_nonexistent_role(self, seeded_db):
        """不存在角色编码应返回None"""
        db = seeded_db
        approver = auto_assign_approver(db, "nonexistent_role")
        assert approver is None

    def test_all_users_disabled(self, seeded_db):
        """角色下所有用户均被禁用时应返回None"""
        db = seeded_db
        # disabled_user 是唯一关联 ops_mgr_role 的已禁用用户
        # 但 ops_mgr_user (active) 也在 ops_mgr_role 下
        # 创建一个只有禁用用户的角色来测试
        lonely_role = Role(name="孤独角色", code="lonely_role", permissions="[]")
        db.add(lonely_role)
        db.flush()
        # 仅关联禁用用户
        disabled_user = db.query(User).filter(User.username == "disabled_mgr").first()
        disabled_user.roles.append(lonely_role)
        db.flush()
        approver = auto_assign_approver(db, "lonely_role")
        assert approver is None


class TestCreateApprovalSteps:
    """测试 create_approval_steps() 审批链步骤创建"""

    def test_single_level_chain(self, seeded_db):
        """单级审批类型（故障降级）应创建1个审批步骤"""
        db = seeded_db
        request = _create_approval_request(db, APPROVAL_TYPE_FAULT_DEGRADE, "SRV-001", "运行", "维修")
        steps = create_approval_steps(db, request)
        assert len(steps) == 1
        assert steps[0].level == 1
        assert steps[0].approver_role == "ops_manager"
        assert steps[0].status == APPROVAL_STEP_PENDING

    def test_multi_level_chain(self, seeded_db):
        """双级审批类型（报废退役）应创建2个审批步骤"""
        db = seeded_db
        request = _create_approval_request(db, APPROVAL_TYPE_RETIREMENT, "SRV-001", "运行", "待报废")
        steps = create_approval_steps(db, request)
        assert len(steps) == 2
        assert steps[0].level == 1
        assert steps[0].approver_role == "ops_manager"
        assert steps[1].level == 2
        assert steps[1].approver_role == "admin"
        # 两个步骤都应为 pending
        assert steps[0].status == APPROVAL_STEP_PENDING
        assert steps[1].status == APPROVAL_STEP_PENDING

    def test_steps_linked_to_request(self, seeded_db):
        """审批步骤应正确关联到审批单"""
        db = seeded_db
        request = _create_approval_request(db, APPROVAL_TYPE_FAULT_DEGRADE, "SRV-001", "运行", "维修")
        steps = create_approval_steps(db, request)
        assert steps[0].request_id == request.id

    def test_unknown_approval_type(self, seeded_db):
        """不存在的审批类型应返回空列表"""
        db = seeded_db
        request = ApprovalRequest(
            request_no="APR-99999999-999",
            approval_type="unknown_type",
            asset_code="SRV-001",
            current_stage="运行",
            target_stage="维修",
            reason="测试未知类型",
            status=APPROVAL_STATUS_DRAFT,
            applicant_id=1,
        )
        db.add(request)
        db.flush()
        steps = create_approval_steps(db, request)
        assert steps == []

    def test_approver_assigned(self, seeded_db):
        """审批步骤应自动指派审批人"""
        db = seeded_db
        request = _create_approval_request(db, APPROVAL_TYPE_FAULT_DEGRADE, "SRV-001", "运行", "维修")
        steps = create_approval_steps(db, request)
        assert steps[0].approver_id is not None
        # 验证指派的审批人确实是对应角色的活跃用户
        approver = db.query(User).filter(User.id == steps[0].approver_id).first()
        assert approver.status == "active"
        role_codes = [r.code for r in approver.roles]
        assert "ops_manager" in role_codes


class TestSubmitApproval:
    """测试 submit_approval() draft→pending + 前置门禁校验"""

    def test_submit_success(self, seeded_db):
        """正常提交：draft→pending，生成审批步骤和通知"""
        db = seeded_db
        request = _create_approval_request(db, APPROVAL_TYPE_FAULT_DEGRADE, "SRV-001", "运行", "维修")
        result = submit_approval(db, request.id)
        assert result.status == APPROVAL_STATUS_PENDING
        assert result.applied_at is not None
        assert result.current_level == 1
        # 验证审批步骤已创建
        steps = db.query(ApprovalStep).filter(ApprovalStep.request_id == request.id).all()
        assert len(steps) == 1
        # 验证通知已创建
        notifications = db.query(ApprovalNotification).filter(ApprovalNotification.request_id == request.id).all()
        assert len(notifications) >= 1

    def test_submit_wrong_status(self, seeded_db):
        """非draft状态提交应抛出异常"""
        db = seeded_db
        request = _create_approval_request(db, APPROVAL_TYPE_FAULT_DEGRADE, "SRV-001", "运行", "维修")
        # 手动改为pending
        request.status = APPROVAL_STATUS_PENDING
        db.commit()
        with pytest.raises(ValueError, match="仅draft状态可提交"):
            submit_approval(db, request.id)

    def test_submit_already_approved(self, seeded_db):
        """已approved的审批单再次提交应抛出异常"""
        db = seeded_db
        request = _create_approval_request(db, APPROVAL_TYPE_FAULT_DEGRADE, "SRV-001", "运行", "维修")
        request.status = APPROVAL_STATUS_APPROVED
        db.commit()
        with pytest.raises(ValueError, match="仅draft状态可提交"):
            submit_approval(db, request.id)

    def test_submit_stage_gate_blocked(self, seeded_db):
        """前置门禁校验失败应阻止提交"""
        db = seeded_db
        # 资产在"规划"阶段，试图跳转到"维修"（不合法跳转）
        request = _create_approval_request(db, APPROVAL_TYPE_RETIREMENT, "SRV-003", "规划", "维修")
        with pytest.raises(ValueError, match="不允许从"):
            submit_approval(db, request.id)

    def test_submit_fault_degrade_skips_stage_gate(self, seeded_db):
        """故障降级审批由审批流授权，可跳过阶段门禁。"""
        db = seeded_db
        request = _create_approval_request(db, APPROVAL_TYPE_FAULT_DEGRADE, "SRV-003", "规划", "维修")

        result = submit_approval(db, request.id)

        assert result.status == APPROVAL_STATUS_PENDING

    def test_submit_nonexistent_request(self, seeded_db):
        """不存在的审批单ID应抛出异常"""
        db = seeded_db
        with pytest.raises(ValueError, match="审批单不存在"):
            submit_approval(db, 99999)

    def test_submit_warranty_renewal_skips_gate(self, seeded_db):
        """维保续保审批（target_stage == current_stage）应跳过阶段门禁"""
        db = seeded_db
        request = _create_approval_request(db, APPROVAL_TYPE_WARRANTY_RENEWAL, "SRV-001", "运行", "运行",
                                           reason="续保审批测试")
        result = submit_approval(db, request.id)
        assert result.status == APPROVAL_STATUS_PENDING

    def test_submit_migration_running_to_transit(self, seeded_db):
        """变更迁移审批（运行→在途）应成功提交"""
        db = seeded_db
        request = _create_approval_request(db, APPROVAL_TYPE_MIGRATION, "SRV-001", "运行", "在途")
        result = submit_approval(db, request.id)
        assert result.status == APPROVAL_STATUS_PENDING


class TestProcessApprovalAction:
    """测试 process_approval_action() approve/reject + 多级流转"""

    def test_approve_single_level(self, seeded_db):
        """单级审批通过：pending→approved，驱动阶段变更"""
        db = seeded_db
        request = _create_approval_request(db, APPROVAL_TYPE_FAULT_DEGRADE, "SRV-001", "运行", "维修")
        submit_approval(db, request.id)
        # 找到审批人
        step = db.query(ApprovalStep).filter(ApprovalStep.request_id == request.id).first()
        result = process_approval_action(db, request.id, "approve", "同意维修", step.approver_id)
        assert result.status == APPROVAL_STATUS_APPROVED
        assert result.approved_at is not None
        # 验证阶段变更
        asset = db.query(Asset).filter(Asset.asset_code == "SRV-001").first()
        assert asset.lifecycle_stage == "维修"

    def test_approve_multi_level_first(self, seeded_db):
        """多级审批一级通过：仍为pending，level升至2"""
        db = seeded_db
        request = _create_approval_request(db, APPROVAL_TYPE_RETIREMENT, "SRV-001", "运行", "待报废")
        submit_approval(db, request.id)
        # 一级审批人通过
        step1 = db.query(ApprovalStep).filter(
            ApprovalStep.request_id == request.id, ApprovalStep.level == 1
        ).first()
        result = process_approval_action(db, request.id, "approve", "一级审批通过", step1.approver_id)
        assert result.status == APPROVAL_STATUS_PENDING
        assert result.current_level == 2

    def test_approve_multi_level_final(self, seeded_db):
        """多级审批全部通过：pending→approved"""
        db = seeded_db
        request = _create_approval_request(db, APPROVAL_TYPE_RETIREMENT, "SRV-001", "运行", "待报废")
        submit_approval(db, request.id)
        # 一级通过
        step1 = db.query(ApprovalStep).filter(
            ApprovalStep.request_id == request.id, ApprovalStep.level == 1
        ).first()
        process_approval_action(db, request.id, "approve", "一级通过", step1.approver_id)
        # 二级通过
        step2 = db.query(ApprovalStep).filter(
            ApprovalStep.request_id == request.id, ApprovalStep.level == 2
        ).first()
        result = process_approval_action(db, request.id, "approve", "二级通过", step2.approver_id)
        assert result.status == APPROVAL_STATUS_APPROVED
        assert result.approved_at is not None
        # 验证阶段变更
        asset = db.query(Asset).filter(Asset.asset_code == "SRV-001").first()
        assert asset.lifecycle_stage == "待报废"

    def test_reject(self, seeded_db):
        """驳回：pending→rejected，必须填写意见"""
        db = seeded_db
        request = _create_approval_request(db, APPROVAL_TYPE_FAULT_DEGRADE, "SRV-001", "运行", "维修")
        submit_approval(db, request.id)
        step = db.query(ApprovalStep).filter(ApprovalStep.request_id == request.id).first()
        result = process_approval_action(db, request.id, "reject", "驳回原因说明", step.approver_id)
        assert result.status == APPROVAL_STATUS_REJECTED
        assert result.rejection_count == 1
        # 验证审批步骤状态
        step = db.query(ApprovalStep).filter(ApprovalStep.request_id == request.id).first()
        assert step.status == APPROVAL_STEP_REJECTED
        assert step.comment == "驳回原因说明"

    def test_reject_requires_comment(self, seeded_db):
        """驳回时未填写意见应抛出异常"""
        db = seeded_db
        request = _create_approval_request(db, APPROVAL_TYPE_FAULT_DEGRADE, "SRV-001", "运行", "维修")
        submit_approval(db, request.id)
        step = db.query(ApprovalStep).filter(ApprovalStep.request_id == request.id).first()
        with pytest.raises(ValueError, match="驳回时必须填写审批意见"):
            process_approval_action(db, request.id, "reject", "", step.approver_id)

    def test_approve_wrong_status(self, seeded_db):
        """对已approved的审批单再次approve应抛出异常"""
        db = seeded_db
        request = _create_approval_request(db, APPROVAL_TYPE_FAULT_DEGRADE, "SRV-001", "运行", "维修")
        submit_approval(db, request.id)
        step = db.query(ApprovalStep).filter(ApprovalStep.request_id == request.id).first()
        # 第一次通过
        process_approval_action(db, request.id, "approve", "通过", step.approver_id)
        # 第二次再次approve
        with pytest.raises(ValueError, match="仅pending状态可审批"):
            process_approval_action(db, request.id, "approve", "再次通过", step.approver_id)

    def test_nonexistent_request(self, seeded_db):
        """不存在的审批单ID应抛出异常"""
        db = seeded_db
        with pytest.raises(ValueError, match="审批单不存在"):
            process_approval_action(db, 99999, "approve", "评论", 1)

    def test_invalid_action(self, seeded_db):
        """不支持的操作类型应抛出异常"""
        db = seeded_db
        request = _create_approval_request(db, APPROVAL_TYPE_FAULT_DEGRADE, "SRV-001", "运行", "维修")
        submit_approval(db, request.id)
        step = db.query(ApprovalStep).filter(ApprovalStep.request_id == request.id).first()
        with pytest.raises(ValueError, match="不支持的操作类型"):
            process_approval_action(db, request.id, "invalid_action", "评论", step.approver_id)

    def test_no_current_step(self, seeded_db):
        """找不到当前审批步骤应抛出异常"""
        db = seeded_db
        request = _create_approval_request(db, APPROVAL_TYPE_FAULT_DEGRADE, "SRV-001", "运行", "维修")
        # 手动设为pending但不创建审批步骤
        request.status = APPROVAL_STATUS_PENDING
        request.current_level = 1
        db.commit()
        with pytest.raises(ValueError, match="找不到当前审批步骤"):
            process_approval_action(db, request.id, "approve", "通过", 1)

    def test_approve_sets_comment_default(self, seeded_db):
        """通过时无意见应默认填充'同意'"""
        db = seeded_db
        request = _create_approval_request(db, APPROVAL_TYPE_FAULT_DEGRADE, "SRV-001", "运行", "维修")
        submit_approval(db, request.id)
        step = db.query(ApprovalStep).filter(ApprovalStep.request_id == request.id).first()
        process_approval_action(db, request.id, "approve", None, step.approver_id)
        step = db.query(ApprovalStep).filter(ApprovalStep.request_id == request.id).first()
        assert step.comment == "同意"

    def test_admin_proxy_approve(self, seeded_db):
        """admin角色可代审批（非指定审批人但admin角色）"""
        db = seeded_db
        request = _create_approval_request(db, APPROVAL_TYPE_FAULT_DEGRADE, "SRV-001", "运行", "维修")
        submit_approval(db, request.id)
        # admin用户（不是指定审批人，但admin角色可代审批）
        admin_user = db.query(User).filter(User.username == "admin").first()
        result = process_approval_action(db, request.id, "approve", "管理员代审批", admin_user.id)
        assert result.status == APPROVAL_STATUS_APPROVED

    def test_wrong_approver_rejected(self, seeded_db):
        """非审批人且非admin角色执行approve应抛出异常"""
        db = seeded_db
        request = _create_approval_request(db, APPROVAL_TYPE_FAULT_DEGRADE, "SRV-001", "运行", "维修")
        submit_approval(db, request.id)
        # 使用viewer用户（无审批权限）
        viewer = db.query(User).filter(User.username == "viewer_user").first()
        with pytest.raises(ValueError, match="您不是当前级别的指定审批人"):
            process_approval_action(db, request.id, "approve", "无权审批", viewer.id)


class TestDriveStageChange:
    """测试 drive_stage_change() 审批通过后阶段变更 + 二次校验"""

    def test_stage_change_success(self, seeded_db):
        """阶段变更成功：资产阶段从运行变为维修"""
        db = seeded_db
        request = _create_approval_request(db, APPROVAL_TYPE_FAULT_DEGRADE, "SRV-001", "运行", "维修")
        submit_approval(db, request.id)
        step = db.query(ApprovalStep).filter(ApprovalStep.request_id == request.id).first()
        process_approval_action(db, request.id, "approve", "通过", step.approver_id)
        asset = db.query(Asset).filter(Asset.asset_code == "SRV-001").first()
        assert asset.lifecycle_stage == "维修"

    def test_stage_change_with_audit_log(self, seeded_db):
        """阶段变更应写入审计日志"""
        db = seeded_db
        request = _create_approval_request(db, APPROVAL_TYPE_FAULT_DEGRADE, "SRV-001", "运行", "维修")
        submit_approval(db, request.id)
        step = db.query(ApprovalStep).filter(ApprovalStep.request_id == request.id).first()
        process_approval_action(db, request.id, "approve", "通过", step.approver_id)
        audit = db.query(AuditLog).filter(AuditLog.resource_id == "SRV-001").first()
        assert audit is not None
        assert audit.action == "stage_change_via_approval"
        assert "运行" in audit.detail
        assert "维修" in audit.detail

    def test_warranty_renewal_no_stage_change(self, seeded_db):
        """维保续保审批（target_stage == current_stage）不变更阶段"""
        db = seeded_db
        request = _create_approval_request(db, APPROVAL_TYPE_WARRANTY_RENEWAL, "SRV-001", "运行", "运行")
        submit_approval(db, request.id)
        step = db.query(ApprovalStep).filter(ApprovalStep.request_id == request.id).first()
        result = process_approval_action(db, request.id, "approve", "通过续保", step.approver_id)
        assert result.status == APPROVAL_STATUS_APPROVED
        # 资产阶段不变
        asset = db.query(Asset).filter(Asset.asset_code == "SRV-001").first()
        assert asset.lifecycle_stage == "运行"

    def test_second_gate_check_blocks_change(self, seeded_db):
        """二次校验失败（并发冲突：资产阶段已被手动修改）应不变更阶段"""
        db = seeded_db
        request = _create_approval_request(db, APPROVAL_TYPE_FAULT_DEGRADE, "SRV-001", "运行", "维修")
        submit_approval(db, request.id)
        # 模拟并发冲突：在审批通过前，有人手动把资产改到了"规划"阶段
        asset = db.query(Asset).filter(Asset.asset_code == "SRV-001").first()
        asset.lifecycle_stage = "规划"
        db.flush()
        # 现在审批通过，但二次校验会发现"规划→维修"不合法
        step = db.query(ApprovalStep).filter(ApprovalStep.request_id == request.id).first()
        result = process_approval_action(db, request.id, "approve", "通过", step.approver_id)
        # 审批单仍标记为approved（审批通过的事实不变）
        assert result.status == APPROVAL_STATUS_APPROVED
        # 但资产阶段不变（仍在规划，因为二次校验失败）
        asset = db.query(Asset).filter(Asset.asset_code == "SRV-001").first()
        assert asset.lifecycle_stage == "规划"


class TestCancelApproval:
    """测试 cancel_approval() 撤回审批"""

    def test_cancel_success(self, seeded_db):
        """正常撤回：pending→cancelled"""
        db = seeded_db
        request = _create_approval_request(db, APPROVAL_TYPE_FAULT_DEGRADE, "SRV-001", "运行", "维修")
        submit_approval(db, request.id)
        result = cancel_approval(db, request.id, request.applicant_id)
        assert result.status == APPROVAL_STATUS_CANCELLED

    def test_cancel_wrong_status(self, seeded_db):
        """非pending状态撤回应抛出异常"""
        db = seeded_db
        request = _create_approval_request(db, APPROVAL_TYPE_FAULT_DEGRADE, "SRV-001", "运行", "维修")
        # draft状态不可撤回
        with pytest.raises(ValueError, match="仅pending状态可撤回"):
            cancel_approval(db, request.id, request.applicant_id)

    def test_cancel_already_approved(self, seeded_db):
        """已approved状态撤回应抛出异常"""
        db = seeded_db
        request = _create_approval_request(db, APPROVAL_TYPE_FAULT_DEGRADE, "SRV-001", "运行", "维修")
        submit_approval(db, request.id)
        step = db.query(ApprovalStep).filter(ApprovalStep.request_id == request.id).first()
        process_approval_action(db, request.id, "approve", "通过", step.approver_id)
        with pytest.raises(ValueError, match="仅pending状态可撤回"):
            cancel_approval(db, request.id, request.applicant_id)

    def test_cancel_wrong_applicant(self, seeded_db):
        """非申请人撤回应抛出异常"""
        db = seeded_db
        request = _create_approval_request(db, APPROVAL_TYPE_FAULT_DEGRADE, "SRV-001", "运行", "维修")
        submit_approval(db, request.id)
        other_user = db.query(User).filter(User.username == "ops_eng").first()
        with pytest.raises(ValueError, match="仅申请人可撤回审批单"):
            cancel_approval(db, request.id, other_user.id)

    def test_cancel_nonexistent(self, seeded_db):
        """不存在的审批单ID应抛出异常"""
        db = seeded_db
        with pytest.raises(ValueError, match="审批单不存在"):
            cancel_approval(db, 99999, 1)

    def test_cancel_creates_notifications(self, seeded_db):
        """撤回应创建通知"""
        db = seeded_db
        request = _create_approval_request(db, APPROVAL_TYPE_FAULT_DEGRADE, "SRV-001", "运行", "维修")
        submit_approval(db, request.id)
        cancel_approval(db, request.id, request.applicant_id)
        notifications = db.query(ApprovalNotification).filter(
            ApprovalNotification.request_id == request.id
        ).all()
        # 应有撤回通知
        cancelled_notifs = [n for n in notifications if n.type == "cancelled"]
        assert len(cancelled_notifs) >= 1


class TestResubmitApproval:
    """测试 resubmit_approval() 驳回后重新提交"""

    def test_resubmit_success(self, seeded_db):
        """重新提交：rejected→draft→pending"""
        db = seeded_db
        request = _create_approval_request(db, APPROVAL_TYPE_FAULT_DEGRADE, "SRV-001", "运行", "维修")
        submit_approval(db, request.id)
        step = db.query(ApprovalStep).filter(ApprovalStep.request_id == request.id).first()
        process_approval_action(db, request.id, "reject", "驳回原因", step.approver_id)
        # 重新提交
        result = resubmit_approval(db, request.id, new_reason="补充原因重新提交")
        assert result.status == APPROVAL_STATUS_PENDING
        assert result.reason == "补充原因重新提交"

    def test_resubmit_clears_old_steps(self, seeded_db):
        """重新提交应清除旧审批步骤并创建新步骤"""
        db = seeded_db
        request = _create_approval_request(db, APPROVAL_TYPE_FAULT_DEGRADE, "SRV-001", "运行", "维修")
        submit_approval(db, request.id)
        step = db.query(ApprovalStep).filter(ApprovalStep.request_id == request.id).first()
        process_approval_action(db, request.id, "reject", "驳回", step.approver_id)
        # 重新提交
        resubmit_approval(db, request.id)
        # 旧步骤应已被清除，新步骤应已创建
        steps = db.query(ApprovalStep).filter(ApprovalStep.request_id == request.id).all()
        assert len(steps) == 1
        assert steps[0].status == APPROVAL_STEP_PENDING

    def test_resubmit_wrong_status(self, seeded_db):
        """非rejected状态重新提交应抛出异常"""
        db = seeded_db
        request = _create_approval_request(db, APPROVAL_TYPE_FAULT_DEGRADE, "SRV-001", "运行", "维修")
        # draft状态不可重新提交
        with pytest.raises(ValueError, match="仅rejected状态可重新提交"):
            resubmit_approval(db, request.id)

    def test_resubmit_nonexistent(self, seeded_db):
        """不存在的审批单ID应抛出异常"""
        db = seeded_db
        with pytest.raises(ValueError, match="审批单不存在"):
            resubmit_approval(db, 99999)

    def test_resubmit_with_attachments(self, seeded_db):
        """重新提交可更新附件"""
        db = seeded_db
        request = _create_approval_request(db, APPROVAL_TYPE_FAULT_DEGRADE, "SRV-001", "运行", "维修")
        submit_approval(db, request.id)
        step = db.query(ApprovalStep).filter(ApprovalStep.request_id == request.id).first()
        process_approval_action(db, request.id, "reject", "驳回", step.approver_id)
        result = resubmit_approval(db, request.id, new_attachments=["file1.pdf", "file2.pdf"])
        assert json.loads(result.attachments) == ["file1.pdf", "file2.pdf"]

    def test_resubmit_preserves_reason_if_none(self, seeded_db):
        """不提供新原因时保留原原因"""
        db = seeded_db
        request = _create_approval_request(db, APPROVAL_TYPE_FAULT_DEGRADE, "SRV-001", "运行", "维修",
                                           reason="原审批原因")
        submit_approval(db, request.id)
        step = db.query(ApprovalStep).filter(ApprovalStep.request_id == request.id).first()
        process_approval_action(db, request.id, "reject", "驳回", step.approver_id)
        result = resubmit_approval(db, request.id)
        assert result.reason == "原审批原因"

    def test_resubmit_increment_rejection_count_preserved(self, seeded_db):
        """驳回次数应在重新提交后保留"""
        db = seeded_db
        request = _create_approval_request(db, APPROVAL_TYPE_FAULT_DEGRADE, "SRV-001", "运行", "维修")
        submit_approval(db, request.id)
        step = db.query(ApprovalStep).filter(ApprovalStep.request_id == request.id).first()
        process_approval_action(db, request.id, "reject", "驳回", step.approver_id)
        assert request.rejection_count == 1
        # 重新提交后驳回次数保留
        result = resubmit_approval(db, request.id)
        assert result.rejection_count == 1


# ========================================================
# P1 - 边界条件与异常
# ========================================================

class TestConcurrentConflict:
    """测试并发冲突场景"""

    def test_asset_stage_changed_between_submit_and_approve(self, seeded_db):
        """审批通过时资产阶段已被手动修改（并发冲突）"""
        db = seeded_db
        request = _create_approval_request(db, APPROVAL_TYPE_FAULT_DEGRADE, "SRV-001", "运行", "维修")
        submit_approval(db, request.id)
        # 模拟并发：在审批操作之前，资产阶段被手动修改为"规划"
        asset = db.query(Asset).filter(Asset.asset_code == "SRV-001").first()
        asset.lifecycle_stage = "规划"
        db.flush()
        # 审批通过：二次校验应发现"规划→维修"不合法
        step = db.query(ApprovalStep).filter(ApprovalStep.request_id == request.id).first()
        result = process_approval_action(db, request.id, "approve", "通过", step.approver_id)
        # 审批单标记approved但阶段不变
        assert result.status == APPROVAL_STATUS_APPROVED
        asset = db.query(Asset).filter(Asset.asset_code == "SRV-001").first()
        assert asset.lifecycle_stage == "规划"

    def test_asset_deleted_between_submit_and_approve(self, seeded_db):
        """审批通过时资产已被删除（极端并发）"""
        db = seeded_db
        request = _create_approval_request(db, APPROVAL_TYPE_FAULT_DEGRADE, "SRV-001", "运行", "维修")
        submit_approval(db, request.id)
        # 模拟：删除资产
        asset = db.query(Asset).filter(Asset.asset_code == "SRV-001").first()
        db.delete(asset)
        db.flush()
        # 审批通过
        step = db.query(ApprovalStep).filter(ApprovalStep.request_id == request.id).first()
        result = process_approval_action(db, request.id, "approve", "通过", step.approver_id)
        # 审批单标记approved（drive_stage_change中asset=None时不crash）
        assert result.status == APPROVAL_STATUS_APPROVED


class TestIllegalStateTransition:
    """测试非法状态转换"""

    def test_approve_on_draft(self, seeded_db):
        """对draft状态的审批单执行approve应抛出异常"""
        db = seeded_db
        request = _create_approval_request(db, APPROVAL_TYPE_FAULT_DEGRADE, "SRV-001", "运行", "维修")
        with pytest.raises(ValueError, match="仅pending状态可审批"):
            process_approval_action(db, request.id, "approve", "评论", 1)

    def test_approve_on_rejected(self, seeded_db):
        """对rejected状态的审批单执行approve应抛出异常"""
        db = seeded_db
        request = _create_approval_request(db, APPROVAL_TYPE_FAULT_DEGRADE, "SRV-001", "运行", "维修")
        submit_approval(db, request.id)
        step = db.query(ApprovalStep).filter(ApprovalStep.request_id == request.id).first()
        process_approval_action(db, request.id, "reject", "驳回", step.approver_id)
        with pytest.raises(ValueError, match="仅pending状态可审批"):
            process_approval_action(db, request.id, "approve", "评论", step.approver_id)

    def test_approve_on_cancelled(self, seeded_db):
        """对cancelled状态的审批单执行approve应抛出异常"""
        db = seeded_db
        request = _create_approval_request(db, APPROVAL_TYPE_FAULT_DEGRADE, "SRV-001", "运行", "维修")
        submit_approval(db, request.id)
        cancel_approval(db, request.id, request.applicant_id)
        with pytest.raises(ValueError, match="仅pending状态可审批"):
            process_approval_action(db, request.id, "approve", "评论", 1)

    def test_submit_on_cancelled(self, seeded_db):
        """对cancelled状态再次提交应抛出异常"""
        db = seeded_db
        request = _create_approval_request(db, APPROVAL_TYPE_FAULT_DEGRADE, "SRV-001", "运行", "维修")
        submit_approval(db, request.id)
        cancel_approval(db, request.id, request.applicant_id)
        with pytest.raises(ValueError, match="仅draft状态可提交"):
            submit_approval(db, request.id)

    def test_cancel_on_rejected(self, seeded_db):
        """对rejected状态执行cancel应抛出异常"""
        db = seeded_db
        request = _create_approval_request(db, APPROVAL_TYPE_FAULT_DEGRADE, "SRV-001", "运行", "维修")
        submit_approval(db, request.id)
        step = db.query(ApprovalStep).filter(ApprovalStep.request_id == request.id).first()
        process_approval_action(db, request.id, "reject", "驳回", step.approver_id)
        with pytest.raises(ValueError, match="仅pending状态可撤回"):
            cancel_approval(db, request.id, request.applicant_id)

    def test_resubmit_on_draft(self, seeded_db):
        """对draft状态执行resubmit应抛出异常"""
        db = seeded_db
        request = _create_approval_request(db, APPROVAL_TYPE_FAULT_DEGRADE, "SRV-001", "运行", "维修")
        with pytest.raises(ValueError, match="仅rejected状态可重新提交"):
            resubmit_approval(db, request.id)

    def test_resubmit_on_approved(self, seeded_db):
        """对approved状态执行resubmit应抛出异常"""
        db = seeded_db
        request = _create_approval_request(db, APPROVAL_TYPE_FAULT_DEGRADE, "SRV-001", "运行", "维修")
        submit_approval(db, request.id)
        step = db.query(ApprovalStep).filter(ApprovalStep.request_id == request.id).first()
        process_approval_action(db, request.id, "approve", "通过", step.approver_id)
        with pytest.raises(ValueError, match="仅rejected状态可重新提交"):
            resubmit_approval(db, request.id)


class TestEmptyApprovalChain:
    """测试空审批链/无审批人场景"""

    def test_unknown_type_no_chain(self, seeded_db):
        """未知审批类型无审批链配置，提交后无步骤"""
        db = seeded_db
        request = ApprovalRequest(
            request_no="APR-99999999-001",
            approval_type="unknown_type",
            asset_code="SRV-001",
            current_stage="运行",
            target_stage="运行",  # 无阶段变更，绕过门禁
            reason="测试未知类型审批",
            status=APPROVAL_STATUS_DRAFT,
            applicant_id=1,
        )
        db.add(request)
        db.flush()
        result = submit_approval(db, request.id)
        assert result.status == APPROVAL_STATUS_PENDING
        # 无审批步骤
        steps = db.query(ApprovalStep).filter(ApprovalStep.request_id == request.id).all()
        assert len(steps) == 0

    def test_no_approver_in_role(self, db_session):
        """角色下无活跃用户时审批步骤approver_id为None"""
        db = db_session
        # 只创建角色，不创建用户
        role = Role(name="空角色", code="empty_role", permissions="[]")
        db.add(role)
        db.flush()
        # 创建资产
        asset = Asset(asset_code="SRV-EMPTY", asset_category="服务器", lifecycle_stage="运行")
        db.add(asset)
        db.flush()
        # 临时添加一个审批模板（替代原 APPROVAL_CHAIN_CONFIG 注入；运行期单一数据源已迁移至 WorkflowTemplate）
        template = WorkflowTemplate(
            approval_type="test_empty_role",
            approval_type_name="测试空角色",
            current_stage="运行",
            target_stage="维修",
            mode="single",
            chain=[{"level": 1, "role": "empty_role"}],
            enabled=True,
        )
        db.add(template)
        db.flush()
        try:
            request = ApprovalRequest(
                request_no="APR-TESTEMPTY-001",
                approval_type="test_empty_role",
                asset_code="SRV-EMPTY",
                current_stage="运行",
                target_stage="维修",
                reason="测试空角色审批",
                status=APPROVAL_STATUS_DRAFT,
                applicant_id=1,
            )
            db.add(request)
            db.flush()
            steps = create_approval_steps(db, request)
            assert len(steps) == 1
            assert steps[0].approver_id is None  # 无活跃用户可指派
        finally:
            # 清理临时模板（避免污染后续测试）
            db.delete(template)
            db.flush()


class TestSameDayMultiRequestNo:
    """测试同日多单号递增"""

    def test_sequential_increment(self, seeded_db):
        """连续创建多个审批单号应正确递增"""
        db = seeded_db
        nos = []
        for i in range(10):
            no = generate_request_no(db)
            # 需要实际创建审批单来让序号持久化
            _create_approval_request(db, APPROVAL_TYPE_FAULT_DEGRADE, "SRV-001", "运行", "维修",
                                     reason=f"递增测试{i}")
            nos.append(no)
        today_str = datetime.now(timezone.utc).strftime("%Y%m%d")
        for i, no in enumerate(nos, 1):
            assert no == f"APR-{today_str}-{i:03d}"

    def test_sequence_three_digit_format(self, seeded_db):
        """序号格式应为3位数字（001, 002, 003）"""
        db = seeded_db
        for i in range(3):
            _create_approval_request(db, APPROVAL_TYPE_FAULT_DEGRADE, "SRV-001", "运行", "维修",
                                     reason=f"格式测试{i}")
        no = generate_request_no(db)
        seq = no.split("-")[-1]
        assert len(seq) == 3
        assert seq.isdigit()


class TestStageGateEdgeCases:
    """测试阶段门禁的边界条件"""

    def test_invalid_transition_planning_to_repair(self, seeded_db):
        """非法跳转：规划→维修（规划只能跳转到在途或上架）"""
        db = seeded_db
        result = check_stage_gate(db, "SRV-003", "维修")
        assert result["allowed"] is False
        assert "不允许从" in result["message"]

    def test_invalid_transition_running_to_planning(self, seeded_db):
        """非法跳转：运行→规划（规划不是运行的合法跳转目标）"""
        db = seeded_db
        result = check_stage_gate(db, "SRV-001", "规划")
        assert result["allowed"] is False

    def test_valid_transition_running_to_repair(self, seeded_db):
        """合法跳转：运行→维修"""
        db = seeded_db
        result = check_stage_gate(db, "SRV-001", "维修")
        assert result["allowed"] is True

    def test_valid_transition_running_to_pending_retire(self, seeded_db):
        """合法跳转：运行→待报废"""
        db = seeded_db
        result = check_stage_gate(db, "SRV-001", "待报废")
        assert result["allowed"] is True

    def test_valid_transition_running_to_transit(self, seeded_db):
        """合法跳转：运行→在途（变更迁移）"""
        db = seeded_db
        result = check_stage_gate(db, "SRV-001", "在途")
        assert result["allowed"] is True

    def test_nonexistent_asset(self, seeded_db):
        """不存在的资产编号应返回不允许"""
        db = seeded_db
        result = check_stage_gate(db, "NONEXIST", "维修")
        assert result["allowed"] is False
        assert "不存在" in result["message"]

    def test_same_stage_transition(self, seeded_db):
        """同阶段跳转（维保续保：运行→运行）应不在门禁检查路径中"""
        # 注意：submit_approval中当target==current时跳过门禁
        # check_stage_gate本身不处理同阶段，但实际逻辑中不调用它
        db = seeded_db
        result = check_stage_gate(db, "SRV-001", "运行")
        # 运行→运行不在合法跳转列表中，门禁检查本身会拒绝
        # 但submit_approval逻辑中target==current时直接跳过门禁
        # 所以这里测试的是check_stage_gate函数本身的行为
        assert result["allowed"] is False


# ========================================================
# P2 - 权限与数据完整性
# ========================================================

class TestPermissionChecks:
    """测试权限相关场景"""

    def test_non_approver_cannot_approve(self, seeded_db):
        """非审批人且非admin角色无法执行approve操作"""
        db = seeded_db
        request = _create_approval_request(db, APPROVAL_TYPE_FAULT_DEGRADE, "SRV-001", "运行", "维修")
        submit_approval(db, request.id)
        # 使用运维工程师（不是指定审批人，也不是admin）
        ops_eng = db.query(User).filter(User.username == "ops_eng").first()
        with pytest.raises(ValueError, match="您不是当前级别的指定审批人"):
            process_approval_action(db, request.id, "approve", "评论", ops_eng.id)

    def test_viewer_cannot_approve(self, seeded_db):
        """只读用户无法执行审批操作"""
        db = seeded_db
        request = _create_approval_request(db, APPROVAL_TYPE_FAULT_DEGRADE, "SRV-001", "运行", "维修")
        submit_approval(db, request.id)
        viewer = db.query(User).filter(User.username == "viewer_user").first()
        with pytest.raises(ValueError, match="您不是当前级别的指定审批人"):
            process_approval_action(db, request.id, "approve", "评论", viewer.id)

    def test_admin_can_proxy_approve(self, seeded_db):
        """admin角色可代审批（即使非指定审批人）"""
        db = seeded_db
        request = _create_approval_request(db, APPROVAL_TYPE_FAULT_DEGRADE, "SRV-001", "运行", "维修")
        submit_approval(db, request.id)
        admin_user = db.query(User).filter(User.username == "admin").first()
        result = process_approval_action(db, request.id, "approve", "管理员代审批", admin_user.id)
        assert result.status == APPROVAL_STATUS_APPROVED

    def test_only_applicant_can_cancel(self, seeded_db):
        """仅申请人可撤回审批单"""
        db = seeded_db
        request = _create_approval_request(db, APPROVAL_TYPE_FAULT_DEGRADE, "SRV-001", "运行", "维修")
        submit_approval(db, request.id)
        # 使用非申请人尝试撤回
        other_user = db.query(User).filter(User.username == "ops_mgr").first()
        with pytest.raises(ValueError, match="仅申请人可撤回审批单"):
            cancel_approval(db, request.id, other_user.id)


class TestStepConsistency:
    """测试审批步骤状态一致性"""

    def test_approved_request_all_steps_approved_or_only_current(self, seeded_db):
        """已approved审批单：多级审批中所有已通过级别的步骤应为approved"""
        db = seeded_db
        request = _create_approval_request(db, APPROVAL_TYPE_RETIREMENT, "SRV-001", "运行", "待报废")
        submit_approval(db, request.id)
        # 一级通过
        step1 = db.query(ApprovalStep).filter(
            ApprovalStep.request_id == request.id, ApprovalStep.level == 1
        ).first()
        process_approval_action(db, request.id, "approve", "一级通过", step1.approver_id)
        # 二级通过
        step2 = db.query(ApprovalStep).filter(
            ApprovalStep.request_id == request.id, ApprovalStep.level == 2
        ).first()
        process_approval_action(db, request.id, "approve", "二级通过", step2.approver_id)
        # 所有步骤应为approved
        steps = db.query(ApprovalStep).filter(ApprovalStep.request_id == request.id).all()
        for step in steps:
            assert step.status == APPROVAL_STEP_APPROVED

    def test_rejected_request_step_rejected(self, seeded_db):
        """已rejected审批单：当前级别步骤应为rejected"""
        db = seeded_db
        request = _create_approval_request(db, APPROVAL_TYPE_FAULT_DEGRADE, "SRV-001", "运行", "维修")
        submit_approval(db, request.id)
        step = db.query(ApprovalStep).filter(ApprovalStep.request_id == request.id).first()
        process_approval_action(db, request.id, "reject", "驳回", step.approver_id)
        step = db.query(ApprovalStep).filter(ApprovalStep.request_id == request.id).first()
        assert step.status == APPROVAL_STEP_REJECTED

    def test_multi_level_partial_approve_step_consistency(self, seeded_db):
        """多级审批一级通过二级待审：步骤状态一致性"""
        db = seeded_db
        request = _create_approval_request(db, APPROVAL_TYPE_RETIREMENT, "SRV-001", "运行", "待报废")
        submit_approval(db, request.id)
        # 一级通过
        step1 = db.query(ApprovalStep).filter(
            ApprovalStep.request_id == request.id, ApprovalStep.level == 1
        ).first()
        process_approval_action(db, request.id, "approve", "一级通过", step1.approver_id)
        # 验证步骤一致性
        steps = db.query(ApprovalStep).filter(ApprovalStep.request_id == request.id).all()
        assert steps[0].status == APPROVAL_STEP_APPROVED  # 一级已通过
        assert steps[1].status == APPROVAL_STEP_PENDING   # 二级待审

    def test_resubmit_creates_new_pending_steps(self, seeded_db):
        """重新提交后所有审批步骤应为pending"""
        db = seeded_db
        request = _create_approval_request(db, APPROVAL_TYPE_FAULT_DEGRADE, "SRV-001", "运行", "维修")
        submit_approval(db, request.id)
        step = db.query(ApprovalStep).filter(ApprovalStep.request_id == request.id).first()
        process_approval_action(db, request.id, "reject", "驳回", step.approver_id)
        resubmit_approval(db, request.id)
        steps = db.query(ApprovalStep).filter(ApprovalStep.request_id == request.id).all()
        for step in steps:
            assert step.status == APPROVAL_STEP_PENDING

    def test_step_has_acted_at_after_action(self, seeded_db):
        """审批操作后步骤应有acted_at时间"""
        db = seeded_db
        request = _create_approval_request(db, APPROVAL_TYPE_FAULT_DEGRADE, "SRV-001", "运行", "维修")
        submit_approval(db, request.id)
        step = db.query(ApprovalStep).filter(ApprovalStep.request_id == request.id).first()
        # approve前acted_at应为None
        assert step.acted_at is None
        process_approval_action(db, request.id, "approve", "通过", step.approver_id)
        step = db.query(ApprovalStep).filter(ApprovalStep.request_id == request.id).first()
        assert step.acted_at is not None


class TestNotificationCreation:
    """测试通知系统"""

    def test_submit_creates_approver_notification(self, seeded_db):
        """提交审批时应通知审批人"""
        db = seeded_db
        request = _create_approval_request(db, APPROVAL_TYPE_FAULT_DEGRADE, "SRV-001", "运行", "维修")
        submit_approval(db, request.id)
        notifications = db.query(ApprovalNotification).filter(
            ApprovalNotification.request_id == request.id,
            ApprovalNotification.type == "pending_approval"
        ).all()
        assert len(notifications) >= 1

    def test_approve_creates_applicant_notification(self, seeded_db):
        """审批通过时应通知申请人"""
        db = seeded_db
        request = _create_approval_request(db, APPROVAL_TYPE_FAULT_DEGRADE, "SRV-001", "运行", "维修")
        submit_approval(db, request.id)
        step = db.query(ApprovalStep).filter(ApprovalStep.request_id == request.id).first()
        process_approval_action(db, request.id, "approve", "通过", step.approver_id)
        notifications = db.query(ApprovalNotification).filter(
            ApprovalNotification.request_id == request.id,
            ApprovalNotification.type == "approved"
        ).all()
        assert len(notifications) >= 1

    def test_reject_creates_applicant_notification(self, seeded_db):
        """审批驳回时应通知申请人"""
        db = seeded_db
        request = _create_approval_request(db, APPROVAL_TYPE_FAULT_DEGRADE, "SRV-001", "运行", "维修")
        submit_approval(db, request.id)
        step = db.query(ApprovalStep).filter(ApprovalStep.request_id == request.id).first()
        process_approval_action(db, request.id, "reject", "驳回", step.approver_id)
        notifications = db.query(ApprovalNotification).filter(
            ApprovalNotification.request_id == request.id,
            ApprovalNotification.type == "rejected"
        ).all()
        assert len(notifications) >= 1

    def test_notification_is_read_default_false(self, seeded_db):
        """新通知默认未读"""
        db = seeded_db
        request = _create_approval_request(db, APPROVAL_TYPE_FAULT_DEGRADE, "SRV-001", "运行", "维修")
        submit_approval(db, request.id)
        notifications = db.query(ApprovalNotification).filter(
            ApprovalNotification.request_id == request.id
        ).all()
        for n in notifications:
            assert n.is_read is False


class TestFullWorkflowIntegration:
    """完整审批工作流端到端测试（单元级别，不依赖HTTP）"""

    def test_full_single_level_workflow(self, seeded_db):
        """完整单级审批流程：创建→提交→通过→阶段变更"""
        db = seeded_db
        # 创建审批单
        request = _create_approval_request(db, APPROVAL_TYPE_FAULT_DEGRADE, "SRV-001", "运行", "维修")
        assert request.status == APPROVAL_STATUS_DRAFT
        # 提交
        result = submit_approval(db, request.id)
        assert result.status == APPROVAL_STATUS_PENDING
        # 通过
        step = db.query(ApprovalStep).filter(ApprovalStep.request_id == request.id).first()
        result = process_approval_action(db, request.id, "approve", "同意维修", step.approver_id)
        assert result.status == APPROVAL_STATUS_APPROVED
        # 验证阶段变更
        asset = db.query(Asset).filter(Asset.asset_code == "SRV-001").first()
        assert asset.lifecycle_stage == "维修"

    def test_full_reject_resubmit_workflow(self, seeded_db):
        """完整驳回重提流程：创建→提交→驳回→重提→通过"""
        db = seeded_db
        request = _create_approval_request(db, APPROVAL_TYPE_FAULT_DEGRADE, "SRV-001", "运行", "维修")
        submit_approval(db, request.id)
        step = db.query(ApprovalStep).filter(ApprovalStep.request_id == request.id).first()
        # 驳回
        process_approval_action(db, request.id, "reject", "驳回", step.approver_id)
        assert db.query(ApprovalRequest).filter(ApprovalRequest.id == request.id).first().status == APPROVAL_STATUS_REJECTED
        # 重新提交
        result = resubmit_approval(db, request.id, new_reason="补充资料后重新提交")
        assert result.status == APPROVAL_STATUS_PENDING
        # 再次通过
        step = db.query(ApprovalStep).filter(ApprovalStep.request_id == request.id).first()
        result = process_approval_action(db, request.id, "approve", "同意", step.approver_id)
        assert result.status == APPROVAL_STATUS_APPROVED
        asset = db.query(Asset).filter(Asset.asset_code == "SRV-001").first()
        assert asset.lifecycle_stage == "维修"

    def test_full_multi_level_workflow(self, seeded_db):
        """完整双级审批流程：创建→提交→一级通过→二级通过→阶段变更"""
        db = seeded_db
        request = _create_approval_request(db, APPROVAL_TYPE_RETIREMENT, "SRV-001", "运行", "待报废")
        submit_approval(db, request.id)
        # 一级通过
        step1 = db.query(ApprovalStep).filter(
            ApprovalStep.request_id == request.id, ApprovalStep.level == 1
        ).first()
        result = process_approval_action(db, request.id, "approve", "一级通过", step1.approver_id)
        assert result.status == APPROVAL_STATUS_PENDING
        assert result.current_level == 2
        # 二级通过
        step2 = db.query(ApprovalStep).filter(
            ApprovalStep.request_id == request.id, ApprovalStep.level == 2
        ).first()
        result = process_approval_action(db, request.id, "approve", "二级通过", step2.approver_id)
        assert result.status == APPROVAL_STATUS_APPROVED
        asset = db.query(Asset).filter(Asset.asset_code == "SRV-001").first()
        assert asset.lifecycle_stage == "待报废"

    def test_full_cancel_workflow(self, seeded_db):
        """完整撤回流程：创建→提交→撤回"""
        db = seeded_db
        request = _create_approval_request(db, APPROVAL_TYPE_MIGRATION, "SRV-001", "运行", "在途")
        submit_approval(db, request.id)
        result = cancel_approval(db, request.id, request.applicant_id)
        assert result.status == APPROVAL_STATUS_CANCELLED
        # 资产阶段不变
        asset = db.query(Asset).filter(Asset.asset_code == "SRV-001").first()
        assert asset.lifecycle_stage == "运行"

    def test_warranty_renewal_full_workflow(self, seeded_db):
        """维保续保完整流程：创建→提交→通过→阶段不变"""
        db = seeded_db
        request = _create_approval_request(db, APPROVAL_TYPE_WARRANTY_RENEWAL, "SRV-001", "运行", "运行",
                                           reason="维保续保申请")
        submit_approval(db, request.id)
        step = db.query(ApprovalStep).filter(ApprovalStep.request_id == request.id).first()
        result = process_approval_action(db, request.id, "approve", "同意续保", step.approver_id)
        assert result.status == APPROVAL_STATUS_APPROVED
        # 资产阶段不变
        asset = db.query(Asset).filter(Asset.asset_code == "SRV-001").first()
        assert asset.lifecycle_stage == "运行"
