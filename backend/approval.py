"""审批工作流核心引擎 - 状态机+审批链+阶段变更驱动+通知生成（新台账模板v1.0）"""
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from sqlalchemy import func
import json

from database import (ApprovalRequest, ApprovalStep, ApprovalNotification,
                       Asset, Retirement, User, Role, AuditLog, record_stage_change)
from validation import check_stage_gate
from constants import (APPROVAL_TYPE_NAMES,
                       APPROVAL_TYPE_FAULT_DEGRADE,
                       APPROVAL_TYPE_RETIREMENT,
                       APPROVAL_TYPE_OUTBOUND,
                       APPROVAL_STATUS_DRAFT, APPROVAL_STATUS_PENDING,
                       APPROVAL_STATUS_APPROVED, APPROVAL_STATUS_REJECTED,
                       APPROVAL_STATUS_CANCELLED,
                       APPROVAL_STEP_PENDING, APPROVAL_STEP_APPROVED,
                       APPROVAL_STEP_REJECTED)
from workflow_engine import WorkflowEngine, auto_assign_approver


def generate_request_no(db: Session) -> str:
    """生成审批单号 APR-YYYYMMDD-SEQ"""
    today = datetime.now(timezone.utc).strftime("%Y%m%d")
    prefix = f"APR-{today}-"
    max_no = db.query(func.max(ApprovalRequest.request_no)).filter(
        ApprovalRequest.request_no.like(f"{prefix}%")
    ).first()
    if max_no and max_no[0]:
        seq = int(max_no[0].split("-")[-1]) + 1
    else:
        seq = 1
    return f"{prefix}{seq:03d}"


# auto_assign_approver 已迁移至 workflow_engine.py，本模块从引擎 import 复用（见顶部 import）。
# 保留该符号以兼容既有调用方（如 tests）。


def create_approval_steps(db: Session, request: ApprovalRequest, approver_ids: list = None) -> list:
    """根据审批模板(WorkflowTemplate)配置创建审批步骤，支持手动指定审批人（委托 WorkflowEngine 解释器）"""
    engine = WorkflowEngine(db)
    return engine.create_steps(request, approver_ids)


def create_notification(db: Session, request_id: int, user_id: int,
                         type: str, title: str, content: str) -> ApprovalNotification:
    """创建审批通知"""
    notification = ApprovalNotification(
        request_id=request_id,
        user_id=user_id,
        type=type,
        title=title,
        content=content,
        is_read=False,
    )
    db.add(notification)
    db.flush()
    return notification


def notify_approver(db: Session, request: ApprovalRequest) -> None:
    """通知当前级别审批人"""
    current_step = db.query(ApprovalStep).filter(
        ApprovalStep.request_id == request.id,
        ApprovalStep.level == request.current_level,
        ApprovalStep.status == APPROVAL_STEP_PENDING,
    ).first()
    if current_step and current_step.approver_id:
        type_name = APPROVAL_TYPE_NAMES.get(request.approval_type, request.approval_type)
        create_notification(
            db, request.id, current_step.approver_id,
            "pending_approval",
            f"待审批：{type_name}",
            f"资产{request.asset_code}的阶段变更申请（{request.current_stage}→{request.target_stage}）需要您审批。原因：{request.reason[:100]}"
        )


def notify_applicant(db: Session, request: ApprovalRequest, type: str, content: str) -> None:
    """通知申请人"""
    type_name = APPROVAL_TYPE_NAMES.get(request.approval_type, request.approval_type)
    title_map = {"approved": "审批通过", "rejected": "审批驳回", "cancelled": "审批已撤回"}
    create_notification(
        db, request.id, request.applicant_id,
        type,
        f"{title_map.get(type, type)}：{type_name}",
        content
    )


def submit_approval(db: Session, request_id: int, approver_ids: list = None) -> ApprovalRequest:
    """提交审批 draft→pending，可指定审批人"""
    request = db.query(ApprovalRequest).filter(ApprovalRequest.id == request_id).first()
    if not request:
        raise ValueError("审批单不存在")
    if request.status != APPROVAL_STATUS_DRAFT:
        raise ValueError(f"当前状态为{request.status}，仅draft状态可提交")

    # BUG-002 修复：前置校验——阶段门禁检查
    # 故障降级审批/维保续保审批/移出报废审批 跳过门禁检查
    skip_gate_types = [
        "fault_degrade_approval",
        "warranty_renewal_approval",
        "outbound_approval",
    ]
    if request.approval_type not in skip_gate_types and request.target_stage != request.current_stage:
        gate_result = check_stage_gate(db, request.asset_code, request.target_stage)
        if not gate_result["allowed"]:
            raise ValueError(gate_result["message"])

    request.status = APPROVAL_STATUS_PENDING
    request.applied_at = datetime.now(timezone.utc)
    request.current_level = 1

    steps = create_approval_steps(db, request, approver_ids)
    notify_approver(db, request)

    db.commit()
    db.refresh(request)
    return request


def process_approval_action(db: Session, request_id: int, action: str,
                             comment: str, approver_id: int) -> ApprovalRequest:
    """处理审批操作 approve/reject"""
    request = db.query(ApprovalRequest).filter(ApprovalRequest.id == request_id).first()
    if not request:
        raise ValueError("审批单不存在")
    if request.status != APPROVAL_STATUS_PENDING:
        raise ValueError(f"当前状态为{request.status}，仅pending状态可审批")

    current_step = db.query(ApprovalStep).filter(
        ApprovalStep.request_id == request_id,
        ApprovalStep.level == request.current_level,
    ).first()

    if not current_step:
        raise ValueError("找不到当前审批步骤")

    approver = db.query(User).filter(User.id == approver_id).first()
    approver_roles = [r.code for r in approver.roles]
    if current_step.approver_id != approver_id and "admin" not in approver_roles:
        raise ValueError("您不是当前级别的指定审批人")

    if action == "reject":
        if not comment:
            raise ValueError("驳回时必须填写审批意见")
        current_step.status = APPROVAL_STEP_REJECTED
        current_step.comment = comment
        current_step.acted_at = datetime.now(timezone.utc)
        request.status = APPROVAL_STATUS_REJECTED
        request.rejection_count += 1
        notify_applicant(db, request, "rejected", f"审批已被驳回。驳回原因：{comment}")
        db.commit()
        db.refresh(request)
        return request

    elif action == "approve":
        current_step.status = APPROVAL_STEP_APPROVED
        current_step.comment = comment or "同意"
        current_step.acted_at = datetime.now(timezone.utc)

        engine = WorkflowEngine(db)
        if engine.has_more_levels(request.approval_type, request.current_level):
            request.current_level += 1
            notify_approver(db, request)
            db.commit()
            db.refresh(request)
            return request
        else:
            request.status = APPROVAL_STATUS_APPROVED
            request.approved_at = datetime.now(timezone.utc)

            drive_stage_change(db, request)

            notify_applicant(db, request, "approved", f"审批已通过。资产{request.asset_code}的阶段已从'{request.current_stage}'变更为'{request.target_stage}'。")

            db.commit()
            db.refresh(request)
            return request

    raise ValueError(f"不支持的操作类型: {action}")


def drive_stage_change(db: Session, request: ApprovalRequest) -> None:
    """审批通过后驱动阶段变更（核心集成点）"""
    if request.target_stage == request.current_stage:
        return

    gate_result = check_stage_gate(db, request.asset_code, request.target_stage)
    if gate_result["allowed"]:
        asset = db.query(Asset).filter(Asset.asset_code == request.asset_code).first()
        if asset:
            old_stage = asset.lifecycle_stage
            asset.lifecycle_stage = request.target_stage
            asset.last_updated = datetime.now(timezone.utc)
            type_name = APPROVAL_TYPE_NAMES.get(request.approval_type, request.approval_type)
            audit = AuditLog(
                user_id=request.applicant_id,
                action="stage_change_via_approval",
                resource_type="asset",
                resource_id=asset.asset_code,
                detail=f"审批单{request.request_no}通过，资产{asset.asset_code}阶段从'{old_stage}'变更为'{request.target_stage}'，审批类型：{type_name}"
            )
            db.add(audit)

            # P2 阶段变更日志：故障降级审批路径跳过（已由 create_fault 写一条「运行→维修」，避免双写/空转）
            if request.approval_type != APPROVAL_TYPE_FAULT_DEGRADE:
                applicant = db.query(User).filter(User.id == request.applicant_id).first()
                operator = applicant.real_name or applicant.username if applicant else "system"
                record_stage_change(
                    db, request.asset_code, request.current_stage, request.target_stage,
                    request.approved_at, operator, type_name, is_backfill=False
                )


def cancel_approval(db: Session, request_id: int, applicant_id: int) -> ApprovalRequest:
    """撤回审批 pending→cancelled"""
    request = db.query(ApprovalRequest).filter(ApprovalRequest.id == request_id).first()
    if not request:
        raise ValueError("审批单不存在")
    if request.status != APPROVAL_STATUS_PENDING:
        raise ValueError(f"当前状态为{request.status}，仅pending状态可撤回")
    if request.applicant_id != applicant_id:
        raise ValueError("仅申请人可撤回审批单")

    request.status = APPROVAL_STATUS_CANCELLED

    current_step = db.query(ApprovalStep).filter(
        ApprovalStep.request_id == request_id,
        ApprovalStep.level == request.current_level,
    ).first()
    if current_step and current_step.approver_id:
        notify_applicant(db, request, "cancelled", f"审批单{request.request_no}已被申请人撤回。")
        create_notification(db, request.id, current_step.approver_id, "cancelled", "审批已撤回", f"资产{request.asset_code}的阶段变更审批已被申请人撤回。")

    db.commit()
    db.refresh(request)
    return request


def resubmit_approval(db: Session, request_id: int, new_reason: str = None,
                       new_attachments: list = None) -> ApprovalRequest:
    """驳回后重新提交 rejected→draft→pending"""
    request = db.query(ApprovalRequest).filter(ApprovalRequest.id == request_id).first()
    if not request:
        raise ValueError("审批单不存在")
    if request.status != APPROVAL_STATUS_REJECTED:
        raise ValueError(f"当前状态为{request.status}，仅rejected状态可重新提交")

    if new_reason:
        request.reason = new_reason
    if new_attachments:
        request.attachments = json.dumps(new_attachments, ensure_ascii=False)

    request.status = APPROVAL_STATUS_DRAFT

    old_steps = db.query(ApprovalStep).filter(ApprovalStep.request_id == request_id).all()
    for step in old_steps:
        db.delete(step)
    db.flush()

    return submit_approval(db, request_id)


def auto_submit_fault_approval(db: Session, asset_code: str, fault_id: int,
                                fault_level: str, applicant_id: int,
                                original_stage: str = None) -> dict:
    """P1/P2-严重故障自动创建故障降级审批单并直接进入pending
    BUG-002/BUG-007 修复：
    - original_stage: 资产变更前的原始阶段
    - 故障降级审批跳过门禁检查
    - P2-严重替代原P2
    """
    request_no = generate_request_no(db)

    asset = db.query(Asset).filter(Asset.asset_code == asset_code).first()
    if not asset:
        return None

    current_stage_for_approval = original_stage or asset.lifecycle_stage

    request = ApprovalRequest(
        request_no=request_no,
        approval_type=APPROVAL_TYPE_FAULT_DEGRADE,
        asset_code=asset_code,
        current_stage=current_stage_for_approval,
        target_stage="维修",
        reason=f"{fault_level}级故障自动提交审批（关联故障记录ID:{fault_id}）",
        attachments="[]",
        status=APPROVAL_STATUS_DRAFT,
        applicant_id=applicant_id,
    )
    db.add(request)
    db.flush()

    try:
        result = submit_approval(db, request.id)
        return {"request_no": result.request_no, "request_id": result.id, "status": result.status}
    except ValueError as e:
        request.status = APPROVAL_STATUS_CANCELLED
        db.commit()
        return {"request_no": request_no, "request_id": request.id, "status": "cancelled", "error": str(e)}


def outbound_retirement_auto_submit(db: Session, asset_code: str, retirement_id: int,
                                     applicant_id: int, reason: str = None) -> dict:
    """移出报废→自动创建retirement_approval审批流并直接进入pending
    - 移出类别为"报废"时自动触发
    - 自动创建Retirement记录 + 提交retirement_approval审批
    - retirement_approval审批跳过门禁检查（审批本身就是授权机制）
    """
    request_no = generate_request_no(db)

    asset = db.query(Asset).filter(Asset.asset_code == asset_code).first()
    if not asset:
        return None

    # 获取资产当前阶段作为current_stage
    current_stage = asset.lifecycle_stage

    # retirement_approval的目标阶段为"待报废"
    target_stage = "待报废"

    request = ApprovalRequest(
        request_no=request_no,
        approval_type=APPROVAL_TYPE_RETIREMENT,
        asset_code=asset_code,
        current_stage=current_stage,
        target_stage=target_stage,
        reason=reason or f"移出报废自动提交审批（关联退役记录ID:{retirement_id}）",
        attachments="[]",
        status=APPROVAL_STATUS_DRAFT,
        applicant_id=applicant_id,
    )
    db.add(request)
    db.flush()

    # 自动提交到pending（移出报废审批跳过门禁检查）
    try:
        result = submit_approval(db, request.id)
        return {"request_no": result.request_no, "request_id": result.id, "status": result.status}
    except ValueError as e:
        request.status = APPROVAL_STATUS_CANCELLED
        db.commit()
        return {"request_no": request_no, "request_id": request.id, "status": "cancelled", "error": str(e)}
