"""审批模板幂等 seed —— 将现状 8 类审批链配置写入 workflow_templates 表。

注意：本文件内联原 APPROVAL_CHAIN_CONFIG 内容（运行期不再 import 该常量为数据源）。
仅在 workflow_templates 表为空时写入，可重复执行（幂等）。
"""
from sqlalchemy.orm import Session

from database import WorkflowTemplate
from constants import (
    APPROVAL_TYPE_PROCUREMENT,
    APPROVAL_TYPE_INSPECTION,
    APPROVAL_TYPE_FAULT_DEGRADE,
    APPROVAL_TYPE_MIGRATION,
    APPROVAL_TYPE_WARRANTY_RENEWAL,
    APPROVAL_TYPE_RETIREMENT,
    APPROVAL_TYPE_INBOUND,
    APPROVAL_TYPE_OUTBOUND,
    APPROVAL_TYPE_NAMES,
)

# 内联原 APPROVAL_CHAIN_CONFIG 内容（与改造前逐字段一致）
SEED_TEMPLATES = [
    {"approval_type": APPROVAL_TYPE_PROCUREMENT, "current_stage": "规划", "target_stage": "在途",
     "mode": "single", "chain": [{"level": 1, "role": "ops_manager"}]},
    {"approval_type": APPROVAL_TYPE_INSPECTION, "current_stage": "在途", "target_stage": "上架",
     "mode": "single", "chain": [{"level": 1, "role": "ops_manager"}]},
    {"approval_type": APPROVAL_TYPE_FAULT_DEGRADE, "current_stage": "*", "target_stage": "维修",
     "mode": "single", "chain": [{"level": 1, "role": "ops_manager"}]},
    {"approval_type": APPROVAL_TYPE_MIGRATION, "current_stage": "运行", "target_stage": "在途",
     "mode": "single", "chain": [{"level": 1, "role": "ops_manager"}]},
    {"approval_type": APPROVAL_TYPE_WARRANTY_RENEWAL, "current_stage": "运行", "target_stage": "运行",
     "mode": "single", "chain": [{"level": 1, "role": "ops_manager"}]},
    {"approval_type": APPROVAL_TYPE_RETIREMENT, "current_stage": "运行", "target_stage": "待报废",
     "mode": "multi", "chain": [{"level": 1, "role": "ops_manager"}, {"level": 2, "role": "admin"}]},
    {"approval_type": APPROVAL_TYPE_INBOUND, "current_stage": "规划", "target_stage": "上架",
     "mode": "single", "chain": [{"level": 1, "role": "ops_manager"}]},
    {"approval_type": APPROVAL_TYPE_OUTBOUND, "current_stage": "运行", "target_stage": "待报废",
     "mode": "single", "chain": [{"level": 1, "role": "ops_manager"}]},
]


def seed_workflow_templates(db: Session) -> int:
    """幂等写入 8 类初始模板；返回本次写入数量（已存在则 0）。"""
    existing = db.query(WorkflowTemplate).count()
    if existing > 0:
        return 0
    for item in SEED_TEMPLATES:
        template = WorkflowTemplate(
            approval_type=item["approval_type"],
            approval_type_name=APPROVAL_TYPE_NAMES[item["approval_type"]],
            current_stage=item["current_stage"],
            target_stage=item["target_stage"],
            mode=item["mode"],
            chain=item["chain"],
            enabled=True,
            remark="系统初始化模板（由 seed_workflow_templates 写入）",
        )
        db.add(template)
    db.commit()
    return len(SEED_TEMPLATES)
