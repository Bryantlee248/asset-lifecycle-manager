"""系统配置模块 P1 幂等 seed —— 将现状硬编码矩阵（valid_transitions + 4 类前置条件）写入 stage_transition_rule 表。

仅当 stage_transition_rule 表为空时写入 11 行（is_system=True）；可重复执行（幂等），
与 seed_config_dict / seed_workflow_templates 对称。

映射依据：
  * 11 对允许跳转见 design §5 / PRD §6.2；
  * 前置条件标志映射见 design §3.4 / PRD §6.3（require_inspection/require_location/
    require_fault_record/require_retirement+require_data_cleared 按现状，其余 false）；
  * require_approval 全 true（O5 默认，仅落库，P1 门禁不消费）。
"""
from sqlalchemy.orm import Session

from database import StageTransitionRule


# ============ 阶段流转矩阵（11 对，与改造前 check_stage_gate 逐条一致） ============
# (from_stage, to_stage, require_retirement, require_data_cleared,
#  require_inspection, require_location, require_fault_record)
SEED_TRANSITIONS = [
    ("规划", "在途", False, False, False, False, False),
    ("规划", "上架", False, False, False, False, False),
    ("在途", "上架", False, False, True, False, False),
    ("在途", "运行", False, False, False, False, False),
    ("上架", "运行", False, False, False, True, False),
    ("运行", "维修", False, False, False, False, False),
    ("运行", "待报废", False, False, False, False, False),
    ("运行", "在途", False, False, False, False, False),
    ("维修", "运行", False, False, False, False, True),
    ("维修", "待报废", False, False, False, False, False),
    ("待报废", "已报废", True, True, False, False, False),
]


def seed_stage_transitions(db: Session) -> int:
    """幂等写入 11 条阶段流转规则；返回本次写入数量（已存在则 0）。"""
    existing = db.query(StageTransitionRule).count()
    if existing > 0:
        return 0
    for idx, (from_stage, to_stage, req_ret, req_data, req_insp, req_loc, req_fault) in enumerate(SEED_TRANSITIONS):
        db.add(StageTransitionRule(
            from_stage=from_stage,
            to_stage=to_stage,
            allowed=True,
            require_approval=True,
            require_fault_record=req_fault,
            require_data_cleared=req_data,
            require_retirement=req_ret,
            require_inspection=req_insp,
            require_location=req_loc,
            remark="系统初始化规则（由 seed_stage_transitions 写入）",
            is_system=True,
            sort_order=idx + 1,
        ))
    db.commit()
    return len(SEED_TRANSITIONS)
