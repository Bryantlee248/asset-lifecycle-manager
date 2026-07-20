"""系统配置模块 P2 幂等 seed —— 将现状硬编码的 10 项校验开关与 11 个聚合维度白名单写入 DB。

仅当对应表为空时写入（两张表独立判断，幂等），与 seed_stage_transitions / seed_config_dict 对称。
映射依据：
  * 校验开关 10 项见 design §5.1 / PRD §7.2（rule_key 与 run_all_checks 各检查分支一一对应）；
  * 聚合白名单 11 字段见 design §5.2 / PRD §7.4（与原 AGGREGATE_FIELD_WHITELIST 完全一致）。
所有 seed 行 is_system=True、enabled=True（=现状常开行为），保证存量零误伤。
"""
from sqlalchemy.orm import Session

from database import ValidationRuleSwitch, AggregateWhitelist


# ============ 校验规则开关（10 项，与改造前 run_all_checks 逐条一致） ============
# (rule_key, check_name, description, severity)
SEED_VALIDATION_RULES = [
    ("empty_code", "编号为空", "资产编号为空", "严重"),
    ("empty_sn", "SN号为空", "非报废阶段 SN 序列号为空", "严重"),
    ("empty_position", "位置为空", "非报废阶段 机房/机柜/U位任一为空", "严重"),
    ("empty_responsible", "责任人为空", "上架/运行/维修阶段无责任人", "中等"),
    ("empty_stage", "阶段为空", "生命周期阶段为空", "严重"),
    ("duplicate_code", "编号重复", "资产编号出现>1次", "严重"),
    ("warranty_expired", "维保已过期(运行状态)", "运行阶段维保已过期", "中等"),
    ("warranty_date_invalid", "维保到期日早于入场日期", "warranty_expire_date < entry_date", "严重"),
    ("retired_no_record", "已报废但报废表无记录", "阶段=已报废 且 Retirement 表无记录", "严重"),
    ("orphan_subtable_code", "分表编号不在主表中", "7 个子表 asset_code 不在 assets 主表", "中等"),
]

# ============ 聚合维度白名单（11 字段，与原 AGGREGATE_FIELD_WHITELIST 一致） ============
# (field_key, field_label)
SEED_AGGREGATE_FIELDS = [
    ("lifecycle_stage", "生命周期阶段"),
    ("asset_category", "资产分类"),
    ("room", "机房"),
    ("cabinet", "机柜"),
    ("department", "所属部门"),
    ("ownership", "产权归属"),
    ("brand", "品牌"),
    ("model", "型号"),
    ("responsible_person", "责任人"),
    ("warranty_status", "维保状态"),
    ("project_name", "项目名称"),
]


def seed_p2_config(db: Session) -> tuple:
    """幂等写入校验开关与聚合白名单；返回 (本次写入校验开关数, 本次写入聚合维度数)。

    两张表独立判断空表，已 seed 的表跳过（幂等），未 seed 的表写入。
    """
    seeded_rules = 0
    if db.query(ValidationRuleSwitch).count() == 0:
        for idx, (rule_key, check_name, description, severity) in enumerate(SEED_VALIDATION_RULES):
            db.add(ValidationRuleSwitch(
                rule_key=rule_key,
                check_name=check_name,
                description=description,
                severity=severity,
                enabled=True,
                remark="系统初始化校验规则（由 seed_p2_config 写入）",
                is_system=True,
                sort_order=idx + 1,
            ))
        seeded_rules = len(SEED_VALIDATION_RULES)

    seeded_fields = 0
    if db.query(AggregateWhitelist).count() == 0:
        for idx, (field_key, field_label) in enumerate(SEED_AGGREGATE_FIELDS):
            db.add(AggregateWhitelist(
                field_key=field_key,
                field_label=field_label,
                metric_support="count,original_value",
                enabled=True,
                remark="系统初始化聚合维度（由 seed_p2_config 写入）",
                is_system=True,
                sort_order=idx + 1,
            ))
        seeded_fields = len(SEED_AGGREGATE_FIELDS)

    db.commit()
    return seeded_rules, seeded_fields
