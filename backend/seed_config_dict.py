"""系统配置模块 P0 幂等 seed —— 将原有 constants.py 枚举与分类映射写入字典/分类表。

仅当 dictionary_groups 表为空时写入 17 分组 + 枚举值 + 10 分类（is_system=True）。
可重复执行（幂等），与 seed_workflow_templates 对称。

注意：本文件内联原资产分类与枚举常量内容（运行期不再 import 其为数据源）。
分类 seed 以 main.py 移入局部字典为准（含 PDU→PDU 与 配电设备→PDU 两项，O6 reconcile）。
"""
from sqlalchemy.orm import Session

from database import DictionaryGroup, Dictionary, Category


# ============ 业务域 / 分组（17 个枚举分组） ============
# (domain_code, domain_name, group_code, group_name, sort_order)
SEED_GROUPS = [
    ("fault_repair", "故障维修", "fault_level", "故障级别", 1),
    ("fault_repair", "故障维修", "handle_method", "处理方式", 2),
    ("fault_repair", "故障维修", "root_cause", "根因分类", 3),

    ("retire", "退役报废", "retire_category", "报废类别", 1),
    ("retire", "退役报废", "disposal_method", "处置方式", 2),
    ("retire", "退役报废", "data_clear_option", "数据清除确认", 3),

    ("move", "移入移出", "receive_type", "接收类型", 1),
    ("move", "移入移出", "outbound_category", "移出类别", 2),
    ("move", "移入移出", "inbound_inspection_result", "移入验收结果", 3),
    ("move", "移入移出", "inspection_result", "验收结果", 4),

    ("warranty", "维保续保", "warranty_type", "维保类型", 1),
    ("warranty", "维保续保", "renewal_decision", "续保决策", 2),

    ("change", "变更迁移", "change_type", "变更类型", 1),
    ("change", "变更迁移", "completion_status", "完成状态", 2),

    ("procurement", "采购入库", "procurement_approval_status", "审批状态", 1),

    ("asset", "资产台账", "warranty_status", "维保状态", 1),
    ("asset", "资产台账", "ownership_type", "产权归属", 2),
]


# ============ 枚举值（group_code -> [(value, code, sort_order, remark)]） ============
SEED_DICTIONARIES = {
    "fault_level": [
        ("P1", None, 1, "最高优先级故障"),
        ("P2-严重", None, 2, "严重故障"),
        ("P3", None, 3, "一般故障"),
        ("P4", None, 4, "轻微故障"),
    ],
    "handle_method": [
        ("现场修复", None, 1, ""),
        ("远程修复", None, 2, ""),
        ("返厂维修", None, 3, ""),
        ("更换设备", None, 4, ""),
        ("重启恢复", None, 5, ""),
        ("其他", None, 6, ""),
    ],
    "root_cause": [
        ("硬件故障", None, 1, ""),
        ("软件故障", None, 2, ""),
        ("人为误操作", None, 3, ""),
        ("环境因素", None, 4, ""),
        ("供应商问题", None, 5, ""),
        ("老化损耗", None, 6, ""),
        ("其他", None, 7, ""),
    ],
    "retire_category": [
        ("报废", None, 1, ""),
        ("捐赠", None, 2, ""),
        ("闲置", None, 3, ""),
    ],
    "disposal_method": [
        ("回收商处理", None, 1, ""),
        ("内部拆解", None, 2, ""),
        ("存放备用", None, 3, ""),
        ("其他", None, 4, ""),
    ],
    "data_clear_option": [
        ("已清除", None, 1, ""),
        ("未清除", None, 2, ""),
        ("不适用", None, 3, ""),
    ],
    "receive_type": [
        ("采购入库", None, 1, ""),
        ("调拨入库", None, 2, ""),
        ("客户托管", None, 3, ""),
        ("返厂维修归还", None, 4, ""),
    ],
    "outbound_category": [
        ("调拨", None, 1, ""),
        ("送修", None, 2, ""),
        ("取回", None, 3, ""),
        ("报废", None, 4, ""),
    ],
    "inbound_inspection_result": [
        ("合格", None, 1, ""),
        ("不合格", None, 2, ""),
    ],
    "inspection_result": [
        ("合格", None, 1, ""),
        ("不合格", None, 2, ""),
        ("待验收", None, 3, ""),
    ],
    "warranty_type": [
        ("整机维保", None, 1, ""),
        ("部件维保", None, 2, ""),
        ("延保服务", None, 3, ""),
        ("现场支持", None, 4, ""),
    ],
    "renewal_decision": [
        ("续保", None, 1, ""),
        ("过保运行", None, 2, ""),
        ("计划报废", None, 3, ""),
        ("评估中", None, 4, ""),
    ],
    "change_type": [
        ("位置迁移", None, 1, ""),
        ("配置变更", None, 2, ""),
    ],
    "completion_status": [
        ("已完成", None, 1, ""),
        ("进行中", None, 2, ""),
        ("驳回", None, 3, ""),
        ("未开始", None, 4, ""),
    ],
    "procurement_approval_status": [
        ("审批中", None, 1, ""),
        ("已通过", None, 2, ""),
        ("已驳回", None, 3, ""),
    ],
    "warranty_status": [
        ("在保", None, 1, ""),
        ("过保", None, 2, ""),
        ("续保中", None, 3, ""),
        ("无维保", None, 4, ""),
    ],
    "ownership_type": [
        ("自有", None, 1, ""),
        ("托管", None, 2, ""),
    ],
}


# ============ 资产分类（10 个；O6：配电设备 与 PDU 均映射 PDU，category_code 不唯一） ============
# (category_name, category_code, sort_order)
SEED_CATEGORIES = [
    ("服务器", "SVR", 1),
    ("网络设备", "NET", 2),
    ("存储设备", "STO", 3),
    ("安全设备", "SEC", 4),
    ("UPS", "UPS", 5),
    ("配电设备", "PDU", 6),
    ("空调", "AC", 7),
    ("KVM", "KVM", 8),
    ("PDU", "PDU", 9),
    ("其他", "OTH", 10),
]


def seed_config_dict(db: Session) -> int:
    """幂等写入 17 分组 + 枚举值 + 10 分类；返回本次写入数量（已存在则 0）。"""
    existing = db.query(DictionaryGroup).count()
    if existing > 0:
        return 0

    for domain_code, domain_name, group_code, group_name, sort_order in SEED_GROUPS:
        db.add(DictionaryGroup(
            domain_code=domain_code,
            domain_name=domain_name,
            group_code=group_code,
            group_name=group_name,
            sort_order=sort_order,
            is_system=True,
        ))

    db.flush()  # 父表（dictionary_groups）先行落库，保证外键 group_code 在插入 dictionaries 时已存在（同一未提交事务内 FK 校验可见）

    for group_code, items in SEED_DICTIONARIES.items():
        for value, code, sort_order, remark in items:
            db.add(Dictionary(
                group_code=group_code,
                value=value,
                code=code,
                sort_order=sort_order,
                enabled=True,
                is_system=True,
                remark=remark or None,
            ))

    db.flush()  # 枚举项（dictionaries）先行落库（FK 依赖 dictionary_groups，已 flush）

    for category_name, category_code, sort_order in SEED_CATEGORIES:
        db.add(Category(
            category_name=category_name,
            category_code=category_code,
            sort_order=sort_order,
            enabled=True,
            is_system=True,
        ))

    db.commit()
    return len(SEED_GROUPS) + sum(len(v) for v in SEED_DICTIONARIES.values()) + len(SEED_CATEGORIES)
