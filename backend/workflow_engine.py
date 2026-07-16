"""审批流引擎 — 通用运行时解释器（阶段1模板数据库化 + 阶段2解释器）

设计要点：
- 运行期唯一数据源为 database.WorkflowTemplate（workflow_templates 表）。
- 严格复刻原 APPROVAL_CHAIN_CONFIG 语义：
    * mode='single'：chain 仅 1 节点，approve 即终态。
    * mode='multi'：按 level 升序逐级推进，全部 approve 才终态（不含并行会签）。
    * current_stage='*'：仅 fault_degrade_approval 允许，创建时资产须处于活跃阶段。
    * warranty_renewal_approval：跳过当前阶段匹配校验（current_stage 仅展示）。
- auto_assign_approver 由 approval.py 迁入，规避循环依赖（本模块仅 import database/constants）。
"""
from typing import List, Optional

from sqlalchemy.orm import Session

from database import (
    WorkflowTemplate, ApprovalRequest, ApprovalStep, Asset, User, Role
)
from constants import (
    APPROVAL_TYPE_WARRANTY_RENEWAL,
    APPROVAL_TYPE_FAULT_DEGRADE,
    APPROVAL_STEP_PENDING,
)


def auto_assign_approver(db: Session, role_code: str) -> Optional[User]:
    """根据角色编码自动指派审批人（取该角色下第一个 active 用户），无则返回 None。"""
    role = db.query(Role).filter(Role.code == role_code).first()
    if not role:
        return None
    for user in role.users:
        if user.status == "active":
            return user
    return None


class WorkflowEngine:
    """无状态审批流解释器：读取 WorkflowTemplate 并生成/推进审批。"""

    def __init__(self, db: Session):
        self.db = db

    # ——— 读取 ———
    def get_template(self, approval_type: str) -> Optional[WorkflowTemplate]:
        """按 approval_type 查找模板（自然键关联，无外键）。"""
        if not approval_type:
            return None
        return self.db.query(WorkflowTemplate).filter(
            WorkflowTemplate.approval_type == approval_type
        ).first()

    def get_template_by_id(self, template_id: int) -> Optional[WorkflowTemplate]:
        return self.db.query(WorkflowTemplate).filter(
            WorkflowTemplate.id == template_id
        ).first()

    def list_templates(self) -> List[WorkflowTemplate]:
        """列出全部模板（按 id 升序，等价于原 APPROVAL_CHAIN_CONFIG 插入顺序）。"""
        return self.db.query(WorkflowTemplate).order_by(WorkflowTemplate.id.asc()).all()

    # ——— 步骤生成（替换原 create_approval_steps）———
    def create_steps(self, request: ApprovalRequest, approver_ids: Optional[list] = None) -> List[ApprovalStep]:
        """根据模板 chain 生成审批步骤；approver_ids 按级别覆盖保留。

        与原 create_approval_steps 行为逐条一致：
        - 每个 chain 节点生成一个 ApprovalStep（level / approver_role 取自节点）。
        - approver_ids[i] 非空时优先指派该用户（须 active），否则按 role 自动指派。
        - 仅 flush，不 commit（由调用方 submit_approval 统一提交）。
        """
        template = self.get_template(request.approval_type)
        if not template:
            return []
        chain = template.get_nodes()
        steps: List[ApprovalStep] = []
        for i, node in enumerate(chain):
            if approver_ids and i < len(approver_ids) and approver_ids[i]:
                approver = self.db.query(User).filter(
                    User.id == approver_ids[i], User.status == "active"
                ).first()
            else:
                approver = auto_assign_approver(self.db, node.get("role"))
            step = ApprovalStep(
                request_id=request.id,
                level=node.get("level"),
                approver_id=approver.id if approver else None,
                approver_role=node.get("role"),
                status=APPROVAL_STEP_PENDING,
            )
            self.db.add(step)
            steps.append(step)
        self.db.flush()
        return steps

    # ——— 推进判断（替换原 process_approval_action 的 config["mode"] 读取）———
    def is_multi_mode(self, approval_type: str) -> bool:
        template = self.get_template(approval_type)
        return bool(template and template.mode == "multi")

    def has_more_levels(self, approval_type: str, current_level: int) -> bool:
        """是否还有下一级审批（multi 且未到末级）。"""
        template = self.get_template(approval_type)
        if not template:
            return False
        chain = template.get_nodes()
        return template.mode == "multi" and current_level < len(chain)

    # ——— 创建校验（替换原 main.create_approval_request 的 config 读取）———
    def validate_stage(self, approval_type: str, asset: Asset) -> None:
        """校验审批类型是否可对该资产发起。不通过抛 ValueError（由调用方转 HTTP 400）。

        覆盖：模板存在性、enabled 停用、阶段匹配、current_stage='*' 活跃阶段集。
        """
        template = self.get_template(approval_type)
        if template is None:
            raise ValueError(f"审批类型 {approval_type} 未配置审批模板，无法发起")
        if not template.enabled:
            raise ValueError(
                f"审批类型「{template.approval_type_name}」已停用，暂时无法发起该类审批"
            )
        # 维保续保审批跳过当前阶段匹配校验（current_stage 仅作展示）
        if approval_type == APPROVAL_TYPE_WARRANTY_RENEWAL:
            return
        required_stage = template.current_stage
        if required_stage == "*":
            # 仅故障降级可用；活跃阶段集与现状 main.py 一致
            if asset.lifecycle_stage not in ["上架", "运行", "在途", "维修"]:
                raise ValueError(
                    f"故障降级审批仅允许上架/运行/在途/维修阶段的资产申请，"
                    f"当前阶段为'{asset.lifecycle_stage}'"
                )
        elif required_stage != asset.lifecycle_stage:
            raise ValueError(
                f"资产当前阶段'{asset.lifecycle_stage}'不匹配审批类型要求的'{required_stage}'"
            )

    def get_target_stage(self, approval_type: str, fallback: str) -> str:
        """返回模板目标阶段；无模板时回退 fallback。"""
        template = self.get_template(approval_type)
        if template and template.target_stage:
            return template.target_stage
        return fallback

    # ——— 模板管理（T5）———
    def update_template(self, template_id: int, data: dict) -> WorkflowTemplate:
        """覆盖更新模板白名单字段（approval_type 锁定不可改）。"""
        template = self.get_template_by_id(template_id)
        if not template:
            raise ValueError("审批模板不存在")

        allowed_fields = ["current_stage", "target_stage", "mode", "chain", "enabled", "remark"]
        for field in allowed_fields:
            if field in data and data[field] is not None:
                setattr(template, field, data[field])

        # 约束1：current_stage 仅故障降级可为 "*"
        if template.current_stage == "*" and template.approval_type != APPROVAL_TYPE_FAULT_DEGRADE:
            raise ValueError("仅故障降级审批的 current_stage 允许为 '*'")

        # mode 取值校验
        if template.mode not in ("single", "multi"):
            raise ValueError("mode 仅允许 'single' 或 'multi'")

        # chain 结构校验（节点 level 连续递增、role 必须存在于 roles 表）
        self._validate_chain(template.chain)

        self.db.commit()
        self.db.refresh(template)
        return template

    def _validate_chain(self, chain) -> None:
        if not isinstance(chain, list) or len(chain) == 0:
            raise ValueError("审批链(chain)不能为空，至少包含 1 个节点")
        for node in chain:
            if not isinstance(node, dict) or "level" not in node or "role" not in node:
                raise ValueError("审批链节点必须包含 level 和 role 字段")
            role = node.get("role")
            if not isinstance(role, str) or not role:
                raise ValueError("审批链节点的 role 必须为非空字符串")
            exists = self.db.query(Role).filter(Role.code == role).first()
            if not exists:
                raise ValueError(f"审批角色 {role} 不存在于角色表中")
        levels = [n.get("level") for n in chain]
        if levels != sorted(levels):
            raise ValueError("审批链 level 必须按升序排列")
        if levels[0] != 1 or any(levels[i] - levels[i - 1] != 1 for i in range(1, len(levels))):
            raise ValueError("审批链 level 必须从 1 开始且连续递增")
