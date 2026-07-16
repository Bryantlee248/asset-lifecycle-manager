# 系统架构设计文档（SDD）：审批流引擎改造 v1.0

- **文档版本**：v1.0
- **作者**：高见远（架构师）
- **适用范围**：阶段 1（审批模板数据库化） + 阶段 2（通用运行时解释器）
- **关联文档**：`deliverables/prd-workflow-engine-v1.md`、`deliverables/class-diagram.mermaid`、`deliverables/sequence-diagram.mermaid`
- **代码事实核对基准**：已 Read 确认 `constants.py` / `approval.py` / `database.py` / `main.py` / `auth.py` 现状（见 §5 事实索引）

---

## 0. 设计结论速览（给主理人/ team-lead）

| 项 | 结论 |
| --- | --- |
| 核心决策：`chain` 存储 | **`WorkflowTemplate` 上的 `JSON` 列**（非拆 `WorkflowNode` 子表）。理由见 §3.3。 |
| 框架 | 沿用 **FastAPI + SQLAlchemy + SQLite**，运行期**零新增依赖**。 |
| 数据源切换 | 移除 `APPROVAL_CHAIN_CONFIG` 运行期引用；改由 `WorkflowTemplate` 单一数据源；原 8 类定义转 seed 脚本。 |
| 前端 | **现有 SPA 零改动**（端点的输入输出契约/权限/错误码保持）。P0-6「管理页面」本期以**后端 API + 权限**交付，可视化 UI 推迟（见 §9 待明确）。 |
| 进行中实例 | 天然隔离：步骤落库在 `ApprovalStep`，进行中实例不回读模板（满足约束 3）。 |
| `auto_assign_approver` | 迁至 `workflow_engine.py`，`approval.py` 改从引擎 import，规避循环依赖。 |
| 表创建 | 复用现有 `Base.metadata.create_all`（database.py 末尾），无需引入迁移框架；数据由幂等 seed 脚本写入。 |
| 任务拆分 | T1 模型+seed → T2 引擎核心 → T3 approval.py 切换 → T4 main.py 切换 → T5 模板管理 API → T6 权限项+admin → T7 回归测试（详见 §7）。 |

---

## Part A：系统设计

### 1. 实现方案

#### 1.1 难点与选型

| 难点 | 方案 |
| --- | --- |
| 审批规则从「代码硬编码」迁到「库可配置」，且运行期动态生效 | 新增 `WorkflowTemplate` 表 + `WorkflowEngine` 解释器；`create_approval_request` / `create_approval_steps` / `process_approval_action` / `approval-config/types` 全部改读模板。 |
| 改造后行为必须与现状**逐条一致**（PRD 行为基线） | 解释器严格复刻现状语义：single=单节点直接终态；multi=按 `chain` level 顺序逐级、全部 approve 才终态；`current_stage="*"` 仅故障降级且限定活跃阶段集；`skip_gate_types` 门禁跳过逻辑原样保留。 |
| 阶段 3（会签/或签/条件网关/超时升级）本期不做，但要预留扩展位 | `chain` 节点 JSON 结构预留 `vote_mode`/`approvers` 字段（本期解释器忽略），未来升级解释器即可，无需改表。 |
| 零新增依赖、零前端改动 | 全沿用现有栈；仅新增 1 个 Python 文件 `workflow_engine.py` 与 1 个 seed 文件；SQLAlchemy `JSON` 类型原生支持 SQLite。 |

**框架/库**：FastAPI、SQLAlchemy、SQLite（沿用）；Pydantic（沿用，端点 schema 复用）；pytest（沿用，回归测试）。**不引入** Alembic / 流程图引擎 / 任何新第三方包。

**架构模式**：保持现有「路由层（main.py）→ 服务层（approval.py / workflow_engine.py）→ 模型层（database.py）」分层；`WorkflowEngine` 作为新的无状态服务类（注入 `Session`），被 `approval.py` 与 `main.py` 调用。

#### 1.2 运行期数据流（一句话）

```
APPROVAL_CHAIN_CONFIG(删)  ──seed──▶  WorkflowTemplate(表)
WorkflowEngine 读 WorkflowTemplate  ──▶  生成 ApprovalStep / 决定推进 / 阶段校验
ApprovalRequest / ApprovalStep / 通知 / 阶段驱动  —— 复用现状，不改结构
```

---

### 2. 文件列表（相对 `backend/`）

| 文件 | 操作 | 说明 |
| --- | --- | --- |
| `database.py` | **修改** | 新增 `WorkflowTemplate` 模型（位于 `ApprovalNotification` 之后、`Base.metadata.create_all` 之前）。`ApprovalRequest`/`ApprovalStep`/`ApprovalNotification` **不改结构**。 |
| `workflow_engine.py` | **新增** | `WorkflowEngine` 类 + 迁来的 `auto_assign_approver`；模板读取/步骤生成/模式判断/阶段校验/目标阶段取值/模板 CRUD。 |
| `approval.py` | **修改** | `create_approval_steps`（L46-67）、`process_approval_action`（L187-193）改调 `WorkflowEngine`；移除 `APPROVAL_CHAIN_CONFIG` import；`auto_assign_approver` 改为从 `workflow_engine` 引入。 |
| `main.py` | **修改** | `create_approval_request`（L1484-1495）阶段校验/目标阶段改读引擎；`/api/approval-config/types`（L1668）改读模板；移除 `APPROVAL_CHAIN_CONFIG` import（L65）；**新增**模板管理端点（§4）。 |
| `constants.py` | **修改** | **删除** `APPROVAL_CHAIN_CONFIG`（L80-92）运行期字典；保留枚举 `APPROVAL_TYPES`、`APPROVAL_TYPE_NAMES`、`APPROVAL_TYPE_*`。 |
| `auth.py` | **修改** | `PERMISSION_DEFINITIONS` 新增 `approval_template:manage`；`PERMISSION_GROUPS`「审批工作流」组追加该项；`DEFAULT_ROLES` 的 `admin` 默认权限加入该项（存量 admin 由 `init_default_data` 权限合并逻辑自动补齐）。 |
| `seed_workflow_templates.py` | **新增** | 幂等 seed：将现状 8 类 `APPROVAL_CHAIN_CONFIG` 内容写入 `WorkflowTemplate`；在 `main.py` 启动（`init_default_data` 之后）调用一次。 |
| `main.py`（启动钩子） | **修改** | 在现有 `@app.on_event("startup")` 中 `init_default_data(db)` 之后调用 `seed_workflow_templates(db)`。 |
| `tests/test_workflow_engine.py` | **新增** | 回归测试（见 T7）。 |

> 前端：本期**零改动**。模板的「管理」以后端 API 形式提供；若后续需要 UI，单独评估（见 §9）。

---

### 3. 数据模型设计

#### 3.1 `WorkflowTemplate` 表字段

| 字段 | 类型 | 约束 | 来源/说明 |
| --- | --- | --- | --- |
| `id` | Integer | PK, autoincrement | — |
| `approval_type` | String(30) | **unique, not null** | 对齐 `ApprovalRequest.approval_type`；与 `APPROVAL_TYPES` 一一对应 |
| `approval_type_name` | String(50) | not null | 中文名，取 `APPROVAL_TYPE_NAMES` |
| `current_stage` | String(20) | not null | 具体阶段 **或 `"*"`**（仅故障降级） |
| `target_stage` | String(20) | not null | 目标阶段（来自 `LIFECYCLE_STAGES`） |
| `mode` | String(10) | not null, default `'single'` | `single` / `multi` |
| `chain` | JSON | not null | 节点数组，元素 `{level:int, role:str}`（§8 共享知识定义 schema） |
| `enabled` | Boolean | not null, default `True` | P1-1 预留；本期默认 `True`，创建审批单时停用则拒绝（低成本一并实现） |
| `remark` | Text | nullable | 运维备注 |
| `created_at` | DateTime | server_default now() | — |
| `updated_at` | DateTime | server_default now(), onupdate now() | — |

**与 `ApprovalRequest.approval_type` 的关联方式**：通过 `approval_type` 字符串**自然键**关联，**不加外键**。`WorkflowEngine` 以 `db.query(WorkflowTemplate).filter_by(approval_type=...).first()` 查找。理由：`approval_type` 是枚举语义标签，模板是「配置」而非「每请求数据」，外键会强制 1:1 且不利于 seed/审计；现状也以字符串枚举贯穿全栈。

**SQLAlchemy 类型说明**：`chain` 用 `Column(JSON)`（SQLAlchemy 在 SQLite 上以 TEXT 透明序列化/反序列化，复用现有 `from sqlalchemy import ...` 即可）。如部署环境 SQLAlchemy 版本过旧导致 `JSON` 异常，回退为 `Column(Text)` + 在 `WorkflowEngine` 内 `json.loads/dumps`（设计已预留此回退，实现时二选一）。

#### 3.2 决策论证：`chain` 存 JSON 列 vs 拆 `WorkflowNode` 子表

**决策：采用 JSON 列。** 论证如下：

1. **迁移零转换**：现状 `APPROVAL_CHAIN_CONFIG` 的 `chain` 本就是 `[{level, role}, ...]` 嵌套结构，seed 脚本近乎 1:1 直写 `WorkflowTemplate.chain`，无需结构重组，正确性最易保证。
2. **本期查询需求为零**：阶段 1+2 不存在「按节点反查模板」「按角色统计节点」「节点独立权限/审计」等需要跨表索引的场景；节点仅作为模板的「整体配置」被整段读出。
3. **阶段 3 兼容性仍满足**：会签/或签需要节点携带多名审批人/投票模式，只需把节点元素从 `{level, role}` 升级为 `{level, role, vote_mode, approvers}`，JSON 结构可平滑扩展，解释器升级即可，**无需改表**。若拆子表，阶段 3 仍需重构且本期即承担额外复杂度，违背「本期够用 + 简单」原则。
4. **简洁性与低风险**：避免 `WorkflowNode` 子表的 join、级联删除（`ondelete CASCADE`）、`Base.metadata.create_all` 扩容、以及编辑时「先删后插或 diff 更新」的复杂度。符合 PRD 行为基线与硬约束「无版本管理、编辑直接覆盖」——编辑模板即覆盖 `chain` JSON，天然契合。
5. **反方（拆子表）为何不采纳**：仅当节点需作为一等公民被独立检索/版本化/细粒度审计时才占优，而这是阶段 3 之后的事，本期不值得为「尚未到来的需求」提前过度设计（YAGNI）。

**结论**：JSON 列是本期最优解；数据结构已为阶段 3 预留扩展位，未来若确实需要节点级能力，可再加 `WorkflowNode` 子表做迁移（低风险、单向）。

#### 3.3 关键语义约定（也写入 §8 共享知识）

- `mode='single'`：`chain` 仅 1 个节点，approve 即最终通过（state→approved）。
- `mode='multi'`：`chain` 多个节点，按 `level` 升序逐级推进；仅当 `current_level == len(chain)` 且末级 approve 才最终通过。**严格等同现状，不含并行会签**（会签属阶段 3）。
- `current_stage='*'`：仅 `fault_degrade_approval` 允许；创建时要求资产阶段 ∈ `ACTIVE_STAGES`（上架/运行/在途/维修），与现状 `main.py` L1488 一致。
- `warranty_renewal_approval` 创建时**跳过**当前阶段匹配校验（现状 `main.py` L1485 `!= "warranty_renewal_approval"` 分支），模板 `current_stage` 仍填 `"运行"` 仅作展示。
- `enabled=False`：创建该类审批单时拒绝并给明确提示（P1-1 行为，本期低成本一并实现）。

---

### 4. 接口 / 类设计

#### 4.1 `WorkflowEngine`（新增，`workflow_engine.py`）

```python
class WorkflowEngine:
    def __init__(self, db: Session): ...

    # —— 读取 ——
    def get_template(self, approval_type: str) -> WorkflowTemplate | None: ...
    def list_templates(self) -> List[WorkflowTemplate]: ...

    # —— 步骤生成（替换原 create_approval_steps）——
    def create_steps(self, request: ApprovalRequest,
                     approver_ids: list = None) -> List[ApprovalStep]: ...
    # 内部复用 auto_assign_approver(role)，approver_ids 覆盖保留

    # —— 推进判断（替换原 process_approval_action 的 config["mode"] 读取）——
    def is_multi_mode(self, approval_type: str) -> bool: ...
    def has_more_levels(self, approval_type: str, current_level: int) -> bool: ...
    # 末级判定：current_level >= len(chain)

    # —— 创建校验（替换原 main.create_approval_request 的 config 读取）——
    def validate_stage(self, approval_type: str, asset: Asset) -> None:
        # 复用 ACTIVE_STAGES；warranty 跳过；* 校验活跃阶段；否则 == current_stage；不通过抛 ValueError
    def get_target_stage(self, approval_type: str, fallback: str) -> str: ...

    # —— 模板管理 API（T5）——
    def save_template(self, data) -> WorkflowTemplate: ...      # 预留（本期以 update 为主）
    def update_template(self, template_id: int, data) -> WorkflowTemplate: ...
    # 校验：current_stage 仅 fault_degrade 可为 "*"；chain 节点 level 连续递增、role 存在于 roles 表
```

> `auto_assign_approver(db, role_code)` 由 `approval.py` 迁至本文件；`approval.py` 改 `from workflow_engine import WorkflowEngine, auto_assign_approver`。`workflow_engine.py` 仅 import `database` 的模型与 `constants` 的枚举/`ACTIVE_STAGES`，**不 import `approval`**，规避循环依赖。

#### 4.2 `approval.py` 改动点（T3）

- `create_approval_steps`（L46-67）：删除 `config = APPROVAL_CHAIN_CONFIG.get(...)` 分支，改为 `engine = WorkflowEngine(db); engine.create_steps(request, approver_ids)`。**保留** `auto_assign_approver` 的调用语义与 `approver_ids` 覆盖逻辑（移至引擎内）。
- `process_approval_action`（L187-193）：删除 `config = APPROVAL_CHAIN_CONFIG.get(...); if config and config["mode"]=="multi" and current_level < len(config["chain"])`，改为 `if engine.has_more_levels(request.approval_type, request.current_level)`。
- 移除 `from constants import (APPROVAL_CHAIN_CONFIG, ...)` 中 `APPROVAL_CHAIN_CONFIG`；保留其余枚举（仍用于通知/状态机文案）。

#### 4.3 `main.py` 改动点（T4）

- `create_approval_request`（L1484-1495）：
  - `config = APPROVAL_CHAIN_CONFIG.get(...)` → `engine = WorkflowEngine(db)`；
  - 阶段校验逻辑迁移到 `engine.validate_stage(data.approval_type, asset)`；
  - `target_stage = engine.get_target_stage(data.approval_type, current_stage)`。
- `/api/approval-config/types`（L1668）：`for type_code, config in APPROVAL_CHAIN_CONFIG.items()` → `for t in engine.list_templates()`，用 `t.approval_type / approval_type_name / current_stage / target_stage / mode / chain` 构造 `ApprovalTypeConfigItem`（`ApprovalTypeConfigItem` 复用现状 schema，契约不变）。
- 移除 L65 的 `APPROVAL_CHAIN_CONFIG` import。
- **新增模板管理端点（T5）**：
  - `GET /api/approval-templates`（`require_permission("approval_template:manage")`）→ `engine.list_templates()`。
  - `GET /api/approval-templates/{id}`（同上）。
  - `PUT /api/approval-templates/{id}`（同上，`require_permission("approval_template:manage")`）→ `engine.update_template(id, data)`；编辑仅限 `current_stage/target_stage/mode/chain[role增删]`，`approval_type` 锁定不可改（约束 1）。

#### 4.4 类图 / 时序图

见 `deliverables/class-diagram.mermaid` 与 `deliverables/sequence-diagram.mermaid`（已落盘）。

---

### 5. 程序调用流程（关键时序）

**① 用户发起审批**（见 sequence-diagram.mermaid 区块 ①）：
`POST /api/approval-requests` → `WorkflowEngine.validate_stage()` + `get_target_stage()` → 建 `ApprovalRequest(draft)`；`submit` → `approval.submit_approval` → `WorkflowEngine.create_steps()`（读模板 `chain`，按 `role` 指派，支持 `approver_ids` 覆盖）→ `notify_approver`；`action=approve` → `process_approval_action` → `WorkflowEngine.has_more_levels()` 决定「逐级 +1」还是「终态 + drive_stage_change + notify_applicant」。

**② 自动触发路径**（区块 ②）：`auto_submit_fault_approval` / `outbound_retirement_auto_submit` → 建 draft（跳过门禁）→ `submit_approval` → `WorkflowEngine.create_steps()` 读模板生成步骤。原 `skip_gate_types` 门禁跳过逻辑保留在 `submit_approval` 内，不受影响。

**③ 模板管理**（区块 ③）：`GET/PUT /api/approval-templates` 经 `require_permission("approval_template:manage")` 调 `engine.list_templates / update_template`，写库即时对新发起审批生效（无版本、直接覆盖）。

替换关系总结：

| 原代码 | 改造后 |
| --- | --- |
| `approval.py` `create_approval_steps` 读 `APPROVAL_CHAIN_CONFIG` | `WorkflowEngine.create_steps` 读 `WorkflowTemplate.chain` |
| `approval.py` `process_approval_action` 读 `config["mode"]` | `WorkflowEngine.has_more_levels(approval_type, current_level)` |
| `main.py` `create_approval_request` 读 `config` 做阶段校验 | `WorkflowEngine.validate_stage` / `get_target_stage` |
| `main.py` `/api/approval-config/types` 遍历 `config` | `WorkflowEngine.list_templates()` |

---

### 6. 事实索引（已 Read 确认）

| 代码点 | 现状 | 改造动作 |
| --- | --- | --- |
| `constants.py` L80-92 `APPROVAL_CHAIN_CONFIG` | 8 类 dict，含 `current_stage/target_stage/mode/chain`，故障降级 `current_stage="*"` | **删除**（运行期不再 import） |
| `constants.py` L45-64 枚举 | 保留 | 不动 |
| `approval.py` L46-67 `create_approval_steps` | 读 config 硬生成步骤 | 改调 `WorkflowEngine.create_steps` |
| `approval.py` L147-206 `process_approval_action` | L187-193 按 `config["mode"]` 推进 | 改调 `WorkflowEngine.has_more_levels` |
| `approval.py` L115-144 `submit_approval` | 含 `skip_gate_types` 门禁跳过 | 保留，内部步骤生成走引擎 |
| `approval.py` L281-361 自动触发 | 内部调 `submit_approval` | 步骤生成自动走引擎 |
| `main.py` L1478-1512 `create_approval_request` | L1484-1495 读 config 阶段校验+目标阶段 | 改调 `WorkflowEngine.validate_stage/get_target_stage` |
| `main.py` L1664-1675 `/api/approval-config/types` | 遍历 config | 改读 `WorkflowEngine.list_templates` |
| `main.py` L65 import | 引入 `APPROVAL_CHAIN_CONFIG` | 移除 |
| `database.py` L295/319/335 | `ApprovalRequest/ApprovalStep/ApprovalNotification` | **复用不改结构** |
| `auth.py` L182-372 | `PERMISSION_DEFINITIONS/GROUPS/DEFAULT_ROLES` + `init_default_data` 权限合并 | 新增 `approval_template:manage` 并纳入 admin |

---

## Part B：任务分解

### 7. 任务列表（按实现顺序排列，含依赖与角色）

> 角色约定：**架构师**=高见远（设计，已完成）；**工程师**=实现；**测试**=回归。

| 任务 | 名称 | 依赖 | 负责 | 产出 | 验收点 |
| --- | --- | --- | --- | --- | --- |
| **T1** | 数据模型 + 迁移/seed | — | 工程师 | `database.py` 新增 `WorkflowTemplate`；`seed_workflow_templates.py` 幂等写入 8 类；`main.py` 启动钩子调用 seed | ① 表随 `create_all` 自动建；② 8 类模板入库且与 `APPROVAL_CHAIN_CONFIG` 原值逐字段一致；③ 故障降级 `current_stage="*"` 正确保留；④ 旧库启动后模板存在且脚本可重复执行不报错 |
| **T2** | `WorkflowEngine` 核心 | T1 | 工程师 | `workflow_engine.py`：`get_template/list_templates/create_steps/is_multi_mode/has_more_levels/validate_stage/get_target_stage/update_template` + 迁 `auto_assign_approver` | ① 单元验证 single/multi/`*`/warranty 跳过逻辑与现状等价；② `create_steps` 生成的步骤 level/role/approver 与现状一致；③ `enabled=False` 时 `validate_stage` 抛明确错误 |
| **T3** | `approval.py` 切换引用 | T2 | 工程师 | `create_approval_steps`/`process_approval_action` 改调引擎；移除 `APPROVAL_CHAIN_CONFIG` import | ① `approval.py` 不再 import `APPROVAL_CHAIN_CONFIG`；② 手动发起→审批链路（single & multi）与现状逐条一致；③ 驳回/撤回/重提不受影响 |
| **T4** | `main.py` 切换引用 | T2, T3 | 工程师 | `create_approval_request` 阶段校验/目标阶段改读引擎；`/api/approval-config/types` 改读模板；移除 import | ① `/api/approval-config/types` 返回与现状等价；② 阶段校验等价（含 `*` 活跃阶段集、warranty 跳过）；③ 20+ 端点契约/权限/错误码不变 |
| **T5** | 模板管理 API | T1, T2 | 工程师 | `main.py` 新增 `GET/PUT /api/approval-templates`（含 `require_permission("approval_template:manage")`）；编辑仅限基础信息+节点 | ① admin 可查/改模板且即时生效；② 非 admin 调接口返回 403；③ `approval_type` 锁定不可改；④ 节点 role 增删/校验生效 |
| **T6** | 权限项 + admin 角色 | —（可并行早期） | 工程师 | `auth.py` 新增 `approval_template:manage` + 纳入「审批工作流」组 + admin 默认权限；`init_default_data` 合并逻辑自动补存量 admin | ① `PERMISSION_DEFINITIONS` 含该项；② admin 角色（含存量库）启动后含该权限；③ 其它角色不含 |
| **T7** | 回归测试 | T3, T4, T5, T6 | 测试/工程师 | `tests/test_workflow_engine.py`：创建/提交/审批(单&多)/自动触发/配置端点/权限/阶段校验 | ① 历史数据比对：新发起审批步骤与现状一致；② 前端 SPA 零改动验证通过；③ `/api/approval-config/types` 与现状等价断言通过 |

**依赖图**：`T6` 可最早并行；`T1 → T2 → {T3, T4}`；`T5` 依赖 `T1+T2`；`T7` 依赖 `T3/T4/T5/T6` 全部完成。

> 注：硬约束「仅对新发起审批生效」天然满足——进行中实例使用已落库 `ApprovalStep`，不回读模板，无需快照（PRD §6-Q3 已确认此方案）。

---

### 8. 共享知识（跨文件约定，供工程师实现遵循）

- **`chain` JSON schema**（节点数组，元素的固定字段）：
  ```json
  [{"level": 1, "role": "ops_manager"}, {"level": 2, "role": "admin"}]
  ```
  - `level`：正整数，从 1 递增，代表审批顺序；`multi` 模式按 level 升序逐级。
  - `role`：角色 code，必须存在于 `roles` 表（本期仅 `ops_manager`/`admin` 等现有角色）。
  - **阶段 3 预留扩展位（本期解释器忽略，仅占位）**：节点可扩展为 `{"level":int, "role":str, "vote_mode":"AND"|"OR", "approvers":[int]}`；本期 `WorkflowEngine` 仅读 `level`/`role`。
- **`mode` 取值**：`"single"`（单级，1 节点即终态）| `"multi"`（多级，按 level 顺序逐级、全部 approve 才终态；严格等同现状，**不含并行会签**）。
- **`current_stage` 约定**：具体阶段字符串 或 `"*"`；`"*"` **仅 `fault_degrade_approval`（故障降级）可用**，其它类型下拉仅限具体阶段（模板编辑 API 须做该校验）。
- **`enabled` 默认 `True`**；设为 `False` 后该类审批单创建被拒并给明确提示（P1-1 行为，本期低成本实现）。
- **`approval_type` 锁定**：模板编辑不可改 `approval_type` 编码/名称（约束 1）；仅可改 `current_stage/target_stage/mode/chain`。
- **数据源唯一性**：运行期任何步骤/阶段/模式查询**只能**读 `WorkflowTemplate`，禁止重新 import `APPROVAL_CHAIN_CONFIG`；原 8 类定义仅存在于 seed 脚本（与运行期解耦）。
- **复用约定**：`auto_assign_approver(role)` 已迁至 `workflow_engine.py`，`approval.py` 从引擎 import；`skip_gate_types`（fault_degrade/warranty_renewal/outbound）门禁跳过逻辑保留在 `submit_approval` 内。
- **API 契约不变**：`ApprovalTypeConfigItem`、`ApprovalDropdownConfig` 等 schema 复用；前端 SPA 零改动。

---

### 9. 待明确事项（交主理人 / 产品经理拍板）

1. **P0-6「管理页面」范围冲突（重点）**：PRD §0 与 §5.3 明确「前端 SPA 本期零改动」，但 P0-6 又列「后台审批模板管理页面」。按硬约束「前端零改动」，**本期以后端 API（`/api/approval-templates` + `approval_template:manage` 权限）交付**，可视化编辑 UI 建议推迟到后续迭代。**请 PM 确认**：是接受「API + 权限即视为 P0-6 完成」，还是必须本期出一个独立管理页（若需独立页，则违反「前端零改动」契约，需升级决策）。
2. **`enabled` 停用后的具体行为**：本设计按「停用 → 创建该类审批单返回 400 明确提示」实现（P1-1）。若希望「停用后仍可查看历史但禁止新发起」之外的更细行为（如软隐藏），请确认。
3. **`current_stage="*"` UI 隐藏**：模板编辑 API 已强制非故障降级类型不可设 `"*"`；若未来前端做管理页，需对其它类型隐藏该选项（本期前端不动，仅后端校验）。
4. **`WorkflowTemplate` 表中是否冗余存 `approval_type_name`**：本设计冗余存储（便于列表直出、审计），与 `APPROVAL_TYPE_NAMES` 保持一致即可；若希望严格单一来源（name 由枚举实时取），可去掉该列——**建议保留冗余列**（简单、利于审计与未来 allowed_types 扩展）。
5. **`chain` 用 `JSON` 还是 `Text`**：默认 `JSON`（SQLAlchemy 原生 SQLite 支持）；若部署环境 SQLAlchemy 版本过旧导致异常，回退 `Text` + 手动序列化（实现二选一，不影响行为）。

---

### 10. 依赖包

运行期**无新增第三方依赖**。沿用：

```
fastapi            # Web 框架（沿用）
sqlalchemy         # ORM（沿用，JSON 类型原生支持 SQLite）
pydantic           # 数据校验（沿用，端点 schema 复用）
uvicorn            # ASGI 服务器（沿用）
pytest             # 回归测试（沿用）
```

> 不引入 Alembic / 流程引擎 / 任何新包；表创建复用现有 `Base.metadata.create_all`，配置数据由 `seed_workflow_templates.py` 幂等写入。

---

*文档结束。设计方：高见远（software-architect）。仅设计，未改动任何业务代码。*
