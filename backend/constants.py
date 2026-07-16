"""统一下拉选项配置 - 新台账模板v1.0"""

# 注：原 CATEGORIES / 各枚举列表（WARRANTY_STATUSES / FAULT_LEVELS / ...）已迁移至
# dictionary_groups + dictionaries 表（系统配置模块 P0），由 seed_config_dict 幂等写入，
# 运行期经 config_cache 读取，不再以硬编码常量形式存在。
LIFECYCLE_STAGES = ["规划", "在途", "上架", "运行", "维修", "待报废", "已报废"]

# ============ 生命周期阶段常量 ============
STAGE_PLANNING = "规划"
STAGE_IN_TRANSIT = "在途"
STAGE_INSTALLED = "上架"
STAGE_RUNNING = "运行"
STAGE_REPAIR = "维修"
STAGE_PENDING_RETIRE = "待报废"
STAGE_RETIRED = "已报废"
ACTIVE_STAGES = [STAGE_INSTALLED, STAGE_RUNNING, STAGE_REPAIR]

# ============ 自定义字段聚合白名单（低基数字段，10个） ============
# 用于 /api/stats/aggregate 接口，仅允许对白名单内字段做 GROUP BY 聚合
AGGREGATE_FIELD_WHITELIST = [
    "lifecycle_stage", "asset_category", "room", "cabinet", "department",
    "ownership", "brand", "model", "responsible_person", "warranty_status", "project_name",
]

# ============ 审批类型枚举 ============
APPROVAL_TYPE_PROCUREMENT = "procurement_approval"
APPROVAL_TYPE_INSPECTION = "inspection_approval"
APPROVAL_TYPE_FAULT_DEGRADE = "fault_degrade_approval"
APPROVAL_TYPE_MIGRATION = "migration_approval"
APPROVAL_TYPE_WARRANTY_RENEWAL = "warranty_renewal_approval"
APPROVAL_TYPE_RETIREMENT = "retirement_approval"
APPROVAL_TYPE_INBOUND = "inbound_approval"
APPROVAL_TYPE_OUTBOUND = "outbound_approval"

APPROVAL_TYPES = [
    APPROVAL_TYPE_PROCUREMENT,
    APPROVAL_TYPE_INSPECTION,
    APPROVAL_TYPE_FAULT_DEGRADE,
    APPROVAL_TYPE_MIGRATION,
    APPROVAL_TYPE_WARRANTY_RENEWAL,
    APPROVAL_TYPE_RETIREMENT,
    APPROVAL_TYPE_INBOUND,
    APPROVAL_TYPE_OUTBOUND,
]

APPROVAL_TYPE_NAMES = {
    APPROVAL_TYPE_PROCUREMENT: "采购立项审批",
    APPROVAL_TYPE_INSPECTION: "验收确认审批",
    APPROVAL_TYPE_FAULT_DEGRADE: "故障降级审批",
    APPROVAL_TYPE_MIGRATION: "变更迁移审批",
    APPROVAL_TYPE_WARRANTY_RENEWAL: "维保续保审批",
    APPROVAL_TYPE_RETIREMENT: "报废退役审批",
    APPROVAL_TYPE_INBOUND: "资产移入审批",
    APPROVAL_TYPE_OUTBOUND: "资产移出审批",
}

# 审批状态
APPROVAL_STATUS_DRAFT = "draft"
APPROVAL_STATUS_PENDING = "pending"
APPROVAL_STATUS_APPROVED = "approved"
APPROVAL_STATUS_REJECTED = "rejected"
APPROVAL_STATUS_CANCELLED = "cancelled"
APPROVAL_STATUSES = [APPROVAL_STATUS_DRAFT, APPROVAL_STATUS_PENDING, APPROVAL_STATUS_APPROVED, APPROVAL_STATUS_REJECTED, APPROVAL_STATUS_CANCELLED]

# 审批步骤状态
APPROVAL_STEP_PENDING = "pending"
APPROVAL_STEP_APPROVED = "approved"
APPROVAL_STEP_REJECTED = "rejected"

# 审批链配置已迁移至 workflow_templates 表（运行期单一数据源）
# 原 8 类定义（APPROVAL_CHAIN_CONFIG）不再保留：
#   - 数据模型见 backend/database.py: WorkflowTemplate
#   - 解释器见 backend/workflow_engine.py: WorkflowEngine
#   - 初始数据由 backend/seed_workflow_templates.py 幂等写入
# 任何步骤/阶段/模式查询均读取 WorkflowTemplate，禁止重新 import 已被删除的 APPROVAL_CHAIN_CONFIG。
