"""枚举/字典/分类的进程内缓存与引用计数 — 系统配置模块 P0

设计约束（见 design-config-module-P0.md §1.3 / §3.5 / §8）：
  * 仅依赖 database 模型，**禁止 import schemas**（避免循环依赖）。
  * schemas / import_export_reports 反过来 import 本模块。
  * 运行期枚举唯一真相 = dictionaries / categories 表；本模块 `_enum_cache`
    仅为「启动期 / 写后」的内存镜像（仅含 enabled 值）。
"""
from typing import Optional

from sqlalchemy import func

from database import (
    SessionLocal,
    Dictionary, Category,
    Asset, AssetInbound, AssetOutbound, Change,
    Fault, Warranty, Retirement, Procurement,
    StageTransitionRule,
    ValidationRuleSwitch, AggregateWhitelist,
)
from constants import AGGREGATE_FIELD_WHITELIST

# ============ 模块级缓存 ============
_enum_cache: dict = {}            # group_code / "category" -> set(enabled 值)
_category_code_cache: dict = {}   # category_name -> category_code
_stage_rules_cache: list = []    # 阶段流转规则 list[dict]（design §3.4 门禁单一数据源）
_validation_rules_cache: Optional[list] = None   # 校验开关 list[dict]（P2，None=未建）
_aggregate_fields_cache: Optional[list] = None   # 聚合白名单 list[dict]（P2，None=未建）
_initialized: bool = False


# ============ 下拉字段 → 数据源映射（design §3.5） ============
# 字段名 -> (source, key)
#   source == "category"   : 查 categories 表（enabled），key 固定 "category"
#   source == "dict"       : 查 dictionaries 表（enabled），key 为 group_code
#   source == "constants"  : 硬编码常量（仅 lifecycle_stages，O4 不动）
DROPDOWN_FIELD_TO_SOURCE = {
    "categories": ("category", "category"),
    "lifecycle_stages": ("constants", None),
    "warranty_statuses": ("dict", "warranty_status"),
    "inspection_results": ("dict", "inspection_result"),
    "change_types": ("dict", "change_type"),
    "fault_levels": ("dict", "fault_level"),
    "handle_methods": ("dict", "handle_method"),
    "root_causes": ("dict", "root_cause"),
    "renewal_decisions": ("dict", "renewal_decision"),
    "retire_categories": ("dict", "retire_category"),
    "data_clear_options": ("dict", "data_clear_option"),
    "completion_statuses": ("dict", "completion_status"),
    "receive_types": ("dict", "receive_type"),
    "outbound_categories": ("dict", "outbound_category"),
    "procurement_approval_statuses": ("dict", "procurement_approval_status"),
    "warranty_types": ("dict", "warranty_type"),
    "disposal_methods": ("dict", "disposal_method"),
    "ownership_types": ("dict", "ownership_type"),
    "inbound_inspection_results": ("dict", "inbound_inspection_result"),
}


# ============ schemas 字段名 → 组 key（design §1.3 / T4） ============
# 注：inspection_result 双 group 已在 schemas 中用显式组 key 区分处理。
FIELD_TO_GROUP_SCHEMA = {
    "asset_category": "category",
    "fault_level": "fault_level",
    "warranty_status": "warranty_status",
    "ownership": "ownership_type",
    "change_type": "change_type",
    "retire_category": "retire_category",
    "disposal_method": "disposal_method",
    "receive_type": "receive_type",
    "outbound_category": "outbound_category",
    "warranty_type": "warranty_type",
    "renewal_decision": "renewal_decision",
    "approval_status": "procurement_approval_status",
}


# ============ 导入流程字段名 → 组 key（design §1.3 / T4） ============
# 注：导入「验收结果」字段名是 inspection_result，归移入场景，按 inbound_inspection_result 校验。
FIELD_TO_GROUP_IMPORT = {
    "asset_category": "category",
    "warranty_status": "warranty_status",
    "change_type": "change_type",
    "fault_level": "fault_level",
    "handle_method": "handle_method",
    "root_cause": "root_cause",
    "renewal_decision": "renewal_decision",
    "retire_category": "retire_category",
    "data_cleared": "data_clear_option",
    "completion_status": "completion_status",
    "receive_type": "receive_type",
    "ownership": "ownership_type",
    "warranty_type": "warranty_type",
    "outbound_category": "outbound_category",
    "inspection_result": "inbound_inspection_result",
    "approval_status": "procurement_approval_status",
}


# ============ 引用保护映射（design §1.3 难点2 / PRD §6.2.6） ============
REFERENCE_MAP = {
    "category": [(Asset, "asset_category"), (AssetInbound, "asset_category")],
    "fault_level": [(Fault, "fault_level")],
    "warranty_status": [(Asset, "warranty_status")],
    "ownership_type": [(Asset, "ownership"), (AssetInbound, "ownership")],
    "change_type": [(Change, "change_type")],
    "retire_category": [(Retirement, "retire_category")],
    "disposal_method": [(Retirement, "disposal_method")],
    "data_clear_option": [(Retirement, "data_cleared")],
    "receive_type": [(AssetInbound, "receive_type")],
    "inbound_inspection_result": [(AssetInbound, "inspection_result")],
    "outbound_category": [(AssetOutbound, "outbound_category")],
    "warranty_type": [(Warranty, "warranty_type")],
    "renewal_decision": [(Warranty, "renewal_decision")],
    "procurement_approval_status": [(Procurement, "approval_status")],
}


# ============ 缓存构建 / 失效 ============
def build_enum_cache(db) -> None:
    """遍历 dictionaries（enabled）+ categories（enabled）填充分区缓存。lifespan 调用一次。"""
    global _enum_cache, _category_code_cache, _initialized
    _enum_cache = {}
    _category_code_cache = {}

    for group_code, value in db.query(Dictionary.group_code, Dictionary.value).filter(
        Dictionary.enabled == True
    ).all():
        _enum_cache.setdefault(group_code, set()).add(value)

    for cat_name, cat_code in db.query(Category.category_name, Category.category_code).filter(
        Category.enabled == True
    ).all():
        _enum_cache.setdefault("category", set()).add(cat_name)
        _category_code_cache[cat_name] = cat_code

    _initialized = True


def invalidate_and_rebuild(db) -> None:
    """配置写 API 成功后调用，重建缓存（design §8-2）。

    同时重建枚举缓存、阶段流转规则缓存（P1）、校验开关缓存与聚合白名单缓存（P2）。
    """
    build_enum_cache(db)
    build_stage_gate_cache(db)
    build_validation_rules_cache(db)
    build_aggregate_fields_cache(db)


# ============ 阶段流转矩阵缓存（design §3.4 / P1） ============
def build_stage_gate_cache(db) -> None:
    """构建阶段流转规则缓存：全量 stage_transition_rule 行 -> list[dict]（design §3.4）。

    lifespan / 写后 invalidate_and_rebuild 调用；check_stage_gate 优先读此缓存。
    """
    global _stage_rules_cache
    rows = db.query(StageTransitionRule).order_by(
        StageTransitionRule.from_stage,
        StageTransitionRule.sort_order,
        StageTransitionRule.id,
    ).all()
    _stage_rules_cache = [r.to_dict() for r in rows]


def get_gate_rule(from_stage: str, to_stage: str):
    """返回 (from_stage, to_stage) 匹配的规则 dict；无匹配返回 None。"""
    for r in _stage_rules_cache:
        if r.get("from_stage") == from_stage and r.get("to_stage") == to_stage:
            return r
    return None


def get_allowed_targets(from_stage: str) -> list:
    """返回该阶段所有 allowed=true 的出口 to_stage 列表（design §3.4）。"""
    return [
        r["to_stage"] for r in _stage_rules_cache
        if r.get("from_stage") == from_stage and r.get("allowed")
    ]


# ============ 校验规则开关缓存（系统配置模块 P2，design §3.5） ============
def build_validation_rules_cache(db) -> None:
    """构建校验开关缓存：全量 validation_rule_switch 行 -> list[dict]。

    lifespan / 写后 invalidate_and_rebuild 调用；run_all_checks 优先读此缓存。
    """
    global _validation_rules_cache
    rows = db.query(ValidationRuleSwitch).order_by(
        ValidationRuleSwitch.sort_order,
        ValidationRuleSwitch.id,
    ).all()
    _validation_rules_cache = [r.to_dict() for r in rows]


def get_enabled_validation_rule_keys() -> Optional[set]:
    """返回当前 enabled=true 的 rule_key 集合；缓存未建返回 None（design §3.5）。

    返回 None 时调用方应触发 build_validation_rules_cache 并重新读取。
    """
    if _validation_rules_cache is None:
        return None
    return {r["rule_key"] for r in _validation_rules_cache if r.get("enabled")}


# ============ 聚合维度白名单缓存（系统配置模块 P2，design §3.6） ============
def build_aggregate_fields_cache(db) -> None:
    """构建聚合白名单缓存：全量 aggregate_whitelist 行 -> list[dict]。

    lifespan / 写后 invalidate_and_rebuild 调用；get_aggregate 优先读此缓存。
    """
    global _aggregate_fields_cache
    rows = db.query(AggregateWhitelist).order_by(
        AggregateWhitelist.sort_order,
        AggregateWhitelist.id,
    ).all()
    _aggregate_fields_cache = [r.to_dict() for r in rows]


def is_valid_aggregate_field(field: Optional[str]):
    """校验 field 是否为启用中的聚合维度（design §3.6）。

    返回 True/False；缓存未建返回 None（调用方应触发 build 并重新读取）。

    表已建但为空（极端未 seed 场景）时回退常量 AGGREGATE_FIELD_WHITELIST，
    保证聚合接口不崩溃（design §2 保留回退常量）。
    """
    if _aggregate_fields_cache is None:
        return None
    if not _aggregate_fields_cache:
        return field in AGGREGATE_FIELD_WHITELIST
    if field is None:
        return False
    return any(
        r.get("field_key") == field and r.get("enabled")
        for r in _aggregate_fields_cache
    )


def get_enabled_aggregate_fields() -> Optional[list]:
    """返回当前 enabled=true 的聚合维度 [{value, label}]（design §3.6，供统计页下拉）。

    缓存未建返回 None。
    """
    if _aggregate_fields_cache is None:
        return None
    return [
        {"value": r["field_key"], "label": r["field_label"]}
        for r in _aggregate_fields_cache if r.get("enabled")
    ]



# ============ 查询辅助（带健壮回退） ============
def _query_enabled_values(key: str) -> set:
    """缓存缺失时直接查 DB（极端情况下请求早于 lifespan 完成的回退，design §1.3 备注）。"""
    db = SessionLocal()
    try:
        if key == "category":
            rows = db.query(Category.category_name).filter(Category.enabled == True).all()
            return {r[0] for r in rows}
        rows = db.query(Dictionary.value).filter(
            Dictionary.group_code == key, Dictionary.enabled == True
        ).all()
        return {r[0] for r in rows}
    finally:
        db.close()


def is_valid_enum(key: str, value) -> bool:
    """校验 value 是否属于 key 组下 enabled 的枚举值（O(1)，design §8-3）。"""
    if value is None:
        return True
    values = _enum_cache.get(key)
    if values is None:
        values = _query_enabled_values(key)
        _enum_cache[key] = values
    return value in values


def get_enum_values(key: str) -> list:
    """返回 key 组下 enabled 枚举值列表（供下拉 / 模板 tip，design §8-4）。"""
    values = _enum_cache.get(key)
    if values is None:
        values = _query_enabled_values(key)
        _enum_cache[key] = values
    return sorted(values) if values else []


def get_category_code(name: str) -> str:
    """按分类中文名查 category_code；缺省 'OTH'（design §8-10）。"""
    if not name:
        return "OTH"
    code = _category_code_cache.get(name)
    if code:
        return code
    db = SessionLocal()
    try:
        cat = db.query(Category).filter(Category.category_name == name).first()
        return cat.category_code if cat else "OTH"
    finally:
        db.close()


def count_references(db, kind: str, value) -> int:
    """统计 value 被引用记录数（design §8-5）；kind 不在 REFERENCE_MAP 中返回 0（可删）。"""
    refs = REFERENCE_MAP.get(kind)
    if not refs:
        return 0
    total = 0
    for model, col_name in refs:
        col = getattr(model, col_name)
        total += db.query(func.count()).filter(col == value).scalar() or 0
    return total
