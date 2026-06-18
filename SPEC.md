# IT资产全生命周期管理系统 — 完整重建规格文档

> **目标读者：AI编程助手（如Codex/Cursor/Cline等）或人类开发者**
> **目标：从零重建与当前生产系统完全等价的系统，包含所有功能、数据模型、API、前端页面和业务逻辑**

---

## 一、项目概述

### 1.1 项目背景
长乐东南数据中心（1618台设备）IT运维体系咨询项目的交付物之一。系统用于管理数据中心IT资产从规划到报废的全生命周期，实现资产台账、采购入库、变更迁移、故障维修、维保续保、退役报废六大环节的数字化管理。

### 1.2 核心管理理念
- **三铁规则**：无记录不执行 / 单号关联 / 阶段门禁
- **资产编号规则**：`DC-CL-[分类码]-[序号]`（如 DC-CL-SRV-001）
- **阶段门禁（Stage Gate）**：资产生命周期阶段跳转必须满足前置条件
- **13项自动校验**：替代Excel校验仪表盘的数据质量检查

### 1.3 生命周期7阶段
`规划 → 在途 → 上架 → 运行 → 维修 → 待报废 → 已报废`

---

## 二、技术栈

| 层级 | 技术选型 | 版本/说明 |
|------|---------|-----------|
| 后端框架 | FastAPI | Python 3.10+ |
| ORM | SQLAlchemy 2.0 | Declarative Base |
| 数据库 | SQLite | 文件级数据库 `asset_lifecycle.db` |
| 认证 | PyJWT (python-jose) | HS256签名，24小时过期 |
| 密码哈希 | passlib[bcrypt] | bcrypt算法 |
| 数据校验 | Pydantic v2 | BaseModel + Field |
| Excel处理 | openpyxl | 导入导出+模板 |
| Web服务器 | uvicorn | ASGI |
| 前端框架 | Vue 3 | CDN加载，不使用构建工具 |
| UI组件库 | Element Plus 2.9.1 | CDN加载 |
| 图标 | @element-plus/icons-vue 2.3.1 | CDN加载 |

### 2.1 Python依赖清单
```
fastapi>=0.100.0
uvicorn>=0.23.0
sqlalchemy>=2.0.0
pydantic>=2.0.0
PyJWT>=2.8.0
passlib[bcrypt]>=1.7.4
python-multipart>=0.0.6
openpyxl>=3.1.0
```

---

## 三、文件结构

```
asset-lifecycle-manager/
├── start.py                    # 一键启动脚本
├── asset_lifecycle.db          # SQLite数据库（自动创建）
├── README.txt                  # 简要说明
├── backend/
│   ├── main.py                 # FastAPI主应用（所有路由）
│   ├── database.py             # 数据库连接+所有ORM模型
│   ├── schemas.py              # 所有Pydantic模型（请求/响应）
│   ├── auth.py                 # JWT认证+RBAC权限+默认数据初始化
│   ├── validation.py           # 13项校验+阶段门禁逻辑
│   ├── constants.py            # 统一下拉选项常量
│   └── import_export_reports.py # 导入导出+4个报表API
└── frontend/
    └── index.html              # 单文件SPA（Vue3+Element Plus CDN）
```

---

## 四、数据库设计

### 4.1 通用约定
- 所有表使用 SQLAlchemy ORM 定义
- SQLite启用外键约束（`PRAGMA foreign_keys=ON`）
- `created_at` / `updated_at` 使用 `server_default=func.now()`
- 主键统一为 `id: Integer, autoincrement`

### 4.2 表清单（9张表）

#### 4.2.1 users（用户表）

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | Integer | PK, auto | |
| username | String(50) | UNIQUE, NOT NULL | 用户名 |
| password_hash | String(255) | NOT NULL | bcrypt哈希 |
| real_name | String(50) | | 真实姓名 |
| email | String(100) | | 邮箱 |
| phone | String(20) | | 手机号 |
| department | String(50) | | 部门 |
| status | String(20) | default="active" | active/disabled |
| last_login | DateTime | | 最后登录时间 |
| created_at | DateTime | server_default=now | |
| updated_at | DateTime | server_default=now, onupdate=now | |

#### 4.2.2 roles（角色表）

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | Integer | PK, auto | |
| name | String(50) | UNIQUE, NOT NULL | 角色名称 |
| code | String(50) | UNIQUE, NOT NULL | 角色编码 |
| description | String(200) | | 角色描述 |
| permissions | Text | default="[]" | 权限列表JSON数组 |
| is_system | Boolean | default=False | 系统内置角色不可删除 |
| created_at | DateTime | server_default=now | |
| updated_at | DateTime | server_default=now, onupdate=now | |

#### 4.2.3 user_roles（用户角色关联表，多对多）

| 字段 | 类型 | 约束 |
|------|------|------|
| user_id | Integer | FK→users.id, CASCADE, PK |
| role_id | Integer | FK→roles.id, CASCADE, PK |

#### 4.2.4 assets（资产台账主索引）

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | Integer | PK, auto | |
| asset_code | String(30) | UNIQUE, NOT NULL | 资产编号 DC-CL-xxx |
| asset_category | String(20) | NOT NULL | 资产分类 |
| brand | String(50) | | 品牌 |
| model | String(100) | | 型号 |
| sn | String(50) | UNIQUE | SN序列号 |
| location | String(30) | | 位置(机房-列-柜-位) |
| lifecycle_stage | String(20) | NOT NULL, default="规划" | 生命周期阶段 |
| entry_date | Date | | 入场日期 |
| responsible_person | String(30) | | 责任人 |
| warranty_status | String(20) | | 维保状态 |
| warranty_expire_date | Date | | 维保到期日 |
| last_updated | DateTime | server_default=now | |
| ip_address | String(50) | | IP地址 |
| remarks | Text | | 备注 |

#### 4.2.5 procurement（采购入库表）

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | Integer | PK, auto | |
| asset_code | String(30) | FK→assets.asset_code, NOT NULL | |
| purchase_order | String(50) | | 采购单号 |
| contract_no | String(50) | | 合同号 |
| supplier | String(100) | | 供应商 |
| quantity | Integer | default=1 | 数量 |
| unit_price | Float | | 单价 |
| total_price | Float | | 总价（自动计算） |
| arrival_date | Date | | 到货日期 |
| inspector | String(30) | | 验收人 |
| inspection_result | String(20) | | 验收结果 |
| install_date | Date | | 上架日期 |
| remarks | Text | | 备注 |

#### 4.2.6 changes（变更迁移表）

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | Integer | PK, auto | |
| asset_code | String(30) | FK→assets.asset_code, NOT NULL | |
| change_type | String(20) | NOT NULL | 变更类型 |
| old_location | String(30) | | 原位置 |
| new_location | String(30) | | 新位置 |
| old_ip | String(50) | | 原IP |
| new_ip | String(50) | | 新IP |
| old_responsible | String(30) | | 原责任人 |
| new_responsible | String(30) | | 新责任人 |
| change_reason | Text | | 变更原因 |
| approver | String(30) | | 审批人 |
| executor | String(30) | | 执行人 |
| execute_date | Date | | 执行日期 |
| completion_status | String(20) | default="进行中" | 完成状态 |
| remarks | Text | | 备注 |

#### 4.2.7 faults（故障维修表）

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | Integer | PK, auto | |
| asset_code | String(30) | FK→assets.asset_code, NOT NULL | |
| fault_level | String(10) | NOT NULL | 故障等级P1-P4 |
| fault_description | Text | | 故障现象 |
| fault_date | Date | | 故障日期 |
| repair_person | String(30) | | 维修人 |
| handle_method | String(30) | | 处理方式 |
| parts_replaced | Text | | 配件更换记录 |
| root_cause | String(20) | | 根因分类 |
| recovery_date | Date | | 恢复日期 |
| downtime_hours | Float | | 停机时长(小时) |
| is_recurring | Boolean | default=False | 是否复发 |
| remarks | Text | | 备注 |

#### 4.2.8 warranties（维保续保表）

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | Integer | PK, auto | |
| asset_code | String(30) | FK→assets.asset_code, NOT NULL | |
| contract_no | String(50) | | 维保合同编号 |
| coverage | Text | | 覆盖范围 |
| start_date | Date | | 维保起始日 |
| end_date | Date | | 维保到期日 |
| renewal_decision | String(20) | | 续保决策 |
| decision_person | String(30) | | 决策人 |
| decision_date | Date | | 决策日期 |
| renewal_contract_no | String(50) | | 续保合同编号 |
| renewal_start_date | Date | | 续保起始日 |
| renewal_end_date | Date | | 续保到期日 |
| cost | Float | | 维保费用 |
| remarks | Text | | 备注 |

#### 4.2.9 retirements（退役报废表）

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | Integer | PK, auto | |
| asset_code | String(30) | FK→assets.asset_code, NOT NULL | |
| retire_reason | Text | | 报废原因 |
| retire_category | String(20) | | 报废类别 |
| application_no | String(50) | | 报废申请单号 |
| approver | String(30) | | 审批人 |
| approval_date | Date | | 审批日期 |
| uninstall_date | Date | | 下架日期 |
| uninstall_person | String(30) | | 下架人 |
| data_cleared | String(20) | | 数据清除确认 |
| data_clear_person | String(30) | | 数据清除人 |
| disposal_method | String(30) | | 处置方式 |
| residual_value | Float | | 残值回收 |
| remarks | Text | | 备注 |

#### 4.2.10 audit_logs（审计日志表）

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | Integer | PK, auto | |
| user_id | Integer | | 操作用户ID |
| action | String(20) | | create/update/delete |
| resource_type | String(30) | | 资源类型 |
| resource_id | String(50) | | 资源ID/编号 |
| detail | Text | | 操作详情 |
| created_at | DateTime | server_default=now | |

---

## 五、下拉选项常量

```python
CATEGORIES = ["服务器", "网络设备", "存储设备", "安全设备", "UPS", "配电设备", "空调", "KVM", "PDU", "其他"]
LIFECYCLE_STAGES = ["规划", "在途", "上架", "运行", "维修", "待报废", "已报废"]
WARRANTY_STATUSES = ["在保", "过保", "续保中", "无维保"]
INSPECTION_RESULTS = ["合格", "不合格", "待验收"]
CHANGE_TYPES = ["位置变更", "配置变更", "归属变更", "IP变更", "其他"]
FAULT_LEVELS = ["P1", "P2", "P3", "P4"]
HANDLE_METHODS = ["现场修复", "远程修复", "返厂维修", "更换设备", "重启恢复", "其他"]
ROOT_CAUSES = ["硬件故障", "软件故障", "人为误操作", "环境因素", "供应商问题", "老化损耗", "其他"]
RENEWAL_DECISIONS = ["续保", "过保运行", "计划报废", "评估中"]
RETIRE_CATEGORIES = ["正常报废", "损坏报废", "技术淘汰", "其他"]
DATA_CLEAR_OPTIONS = ["已清除", "未清除", "不适用"]
COMPLETION_STATUSES = ["进行中", "已完成", "已取消"]
```

---

## 六、RBAC权限体系

### 6.1 JWT认证配置
- **算法**：HS256
- **密钥**：环境变量 `JWT_SECRET_KEY`，默认值 `dev-only-change-in-production-2024`
- **Token过期**：24小时
- **Token载荷**：`{ "sub": str(user_id), "username": "xxx", "exp": timestamp }`
- **前端传输**：`Authorization: Bearer <token>`

### 6.2 38项细粒度权限（11个分组）

| 分组 | 权限代码 | 权限说明 |
|------|---------|---------|
| 概览 | dashboard:view | 查看数据总览 |
| | validation:view | 查看校验仪表盘 |
| 数据交换 | import_export:view | 查看导入导出 |
| | import_export:import | 执行数据导入 |
| | import_export:export | 执行数据导出 |
| 报表统计 | reports:view | 查看报表统计 |
| 资产台账 | assets:view | 查看资产台账 |
| | assets:create | 新增资产 |
| | assets:edit | 编辑资产 |
| | assets:delete | 删除资产 |
| 采购入库 | procurement:view | 查看采购入库 |
| | procurement:create | 新增采购记录 |
| | procurement:edit | 编辑采购记录 |
| | procurement:delete | 删除采购记录 |
| 变更迁移 | change:view | 查看变更迁移 |
| | change:create | 新增变更记录 |
| | change:edit | 编辑变更记录 |
| | change:delete | 删除变更记录 |
| 故障维修 | fault:view | 查看故障维修 |
| | fault:create | 新增故障记录 |
| | fault:edit | 编辑故障记录 |
| | fault:delete | 删除故障记录 |
| 维保续保 | warranty:view | 查看维保续保 |
| | warranty:create | 新增维保记录 |
| | warranty:edit | 编辑维保记录 |
| | warranty:delete | 删除维保记录 |
| 退役报废 | retirement:view | 查看退役报废 |
| | retirement:create | 新增退役记录 |
| | retirement:edit | 编辑退役记录 |
| | retirement:delete | 删除退役记录 |
| 用户管理 | users:view | 查看用户管理 |
| | users:create | 新增用户 |
| | users:edit | 编辑用户 |
| | users:delete | 删除用户 |
| 角色管理 | roles:view | 查看角色管理 |
| | roles:create | 新增角色 |
| | roles:edit | 编辑角色 |
| | roles:delete | 删除角色 |

### 6.3 四个预设角色

| 角色 | code | 权限数 | 说明 |
|------|------|--------|------|
| 系统管理员 | admin | 38（全部） | 可管理用户和角色 |
| 运维主管 | ops_manager | 28 | 管理所有资产数据，查看报表校验，不可管理用户 |
| 运维工程师 | ops_engineer | 18 | 查看和编辑资产，不可删除，不可管理用户 |
| 只读用户 | viewer | 11 | 仅查看+导出，不可增删改 |

**运维主管权限**：dashboard:view, validation:view, import_export:*, reports:view, assets:*, procurement:*, change:*, fault:*, warranty:*, retirement:*

**运维工程师权限**：dashboard:view, validation:view, import_export:view+export, reports:view, assets:view+create+edit, procurement:view+create+edit, change:view+create+edit, fault:view+create+edit, warranty:view+create+edit, retirement:view+create+edit

**只读用户权限**：dashboard:view, validation:view, import_export:view+export, reports:view, assets:view, procurement:view, change:view, fault:view, warranty:view, retirement:view

### 6.4 默认管理员
- 用户名：`admin`
- 密码：`admin123`
- 真实姓名：系统管理员
- 部门：信息中心
- 角色：系统管理员(admin)

### 6.5 权限检查逻辑
1. `admin` 角色拥有所有权限（无需逐项检查）
2. 其他用户：合并其所有角色的权限列表，逐项检查
3. 系统内置角色（is_system=True）不可删除
4. 系统至少保留一个admin用户
5. 用户不可删除自己

---

## 七、API接口规格

### 7.1 通用约定
- 基础路径：`/api`
- 分页统一格式：`{ "total": int, "page": int, "page_size": int, "items": [] }`
- 错误格式：`{ "detail": "错误信息" }`
- HTTP状态码：200成功，400参数错误，401未认证，403权限不足，404不存在
- CORS：允许所有来源（`allow_origins=["*"]`）
- 认证接口不需要权限；所有业务接口需要JWT+权限

### 7.2 认证接口（4个）

| 方法 | 路径 | 权限 | 说明 | 请求体 | 响应 |
|------|------|------|------|--------|------|
| POST | /api/auth/login | 无 | 用户登录 | `{ username, password }` | `{ token, token_type, user }` |
| GET | /api/auth/me | 登录 | 获取当前用户 | - | UserResponse |
| PUT | /api/auth/change-password | 登录 | 修改密码 | `{ old_password, new_password }` | `{ message }` |
| GET | /api/auth/permissions | 无 | 权限配置 | - | PermissionConfig |

**登录逻辑**：
1. 查找用户 → 验证密码 → 检查status=active
2. 更新last_login
3. 生成JWT Token（payload: sub=用户ID, username）
4. 返回token+UserResponse（含roles和permissions列表）

### 7.3 用户管理接口（5个）

| 方法 | 路径 | 权限 | 说明 |
|------|------|------|------|
| GET | /api/users | users:view | 用户列表（支持search/status筛选+分页） |
| POST | /api/users | users:create | 创建用户（含role_ids分配角色） |
| PUT | /api/users/{user_id} | users:edit | 更新用户（可改密码/角色/状态） |
| DELETE | /api/users/{user_id} | users:delete | 删除用户（不可删自己/最后一个admin） |
| POST | /api/users/{user_id}/reset-password | users:edit | 重置密码（默认123456） |

### 7.4 角色管理接口（4个）

| 方法 | 路径 | 权限 | 说明 |
|------|------|------|------|
| GET | /api/roles | roles:view | 角色列表（含user_count） |
| POST | /api/roles | roles:create | 创建角色（含permissions数组） |
| PUT | /api/roles/{role_id} | roles:edit | 更新角色（名称/描述/权限） |
| DELETE | /api/roles/{role_id} | roles:delete | 删除角色（系统角色/有用户的角色不可删） |

### 7.5 资产台账接口（4+2个）

| 方法 | 路径 | 权限 | 说明 |
|------|------|------|------|
| GET | /api/assets | assets:view | 资产列表（search/category/stage/warranty_status筛选+分页） |
| GET | /api/assets/{asset_code} | assets:view | 资产详情 |
| POST | /api/assets | assets:create | 新增资产（编号唯一性校验） |
| PUT | /api/assets/{asset_id} | assets:edit | 更新资产（阶段变更触发门禁检查） |
| DELETE | /api/assets/{asset_id} | assets:delete | 删除资产 |
| GET | /api/assets/{asset_code}/timeline | assets:view | 资产生命周期时间线 |

**资产列表额外逻辑**：每条资产附加 `warranty_alert` 字段（expired/expiring_soon/normal/none）

### 7.6 采购入库接口（4个）

| 方法 | 路径 | 权限 | 说明 |
|------|------|------|------|
| GET | /api/procurements | procurement:view | 采购列表（asset_code筛选+分页） |
| POST | /api/procurements | procurement:create | 新增采购（自动计算total_price） |
| PUT | /api/procurements/{item_id} | procurement:edit | 更新采购 |
| DELETE | /api/procurements/{item_id} | procurement:delete | 删除采购 |

### 7.7 变更迁移接口（4个）

| 方法 | 路径 | 权限 | 说明 |
|------|------|------|------|
| GET | /api/changes | change:view | 变更列表 |
| POST | /api/changes | change:create | 新增变更 |
| PUT | /api/changes/{item_id} | change:edit | 更新变更 |
| DELETE | /api/changes/{item_id} | change:delete | 删除变更 |

### 7.8 故障维修接口（4个）

| 方法 | 路径 | 权限 | 说明 |
|------|------|------|------|
| GET | /api/faults | fault:view | 故障列表 |
| POST | /api/faults | fault:create | 新增故障（P1/P2自动切换主表阶段为"维修"） |
| PUT | /api/faults/{item_id} | fault:edit | 更新故障 |
| DELETE | /api/faults/{item_id} | fault:delete | 删除故障 |

### 7.9 维保续保接口（4个）

| 方法 | 路径 | 权限 | 说明 |
|------|------|------|------|
| GET | /api/warranties | warranty:view | 维保列表 |
| POST | /api/warranties | warranty:create | 新增维保 |
| PUT | /api/warranties/{item_id} | warranty:edit | 更新维保 |
| DELETE | /api/warranties/{item_id} | warranty:delete | 删除维保 |

### 7.10 退役报废接口（4个）

| 方法 | 路径 | 权限 | 说明 |
|------|------|------|------|
| GET | /api/retirements | retirement:view | 退役列表 |
| POST | /api/retirements | retirement:create | 新增退役 |
| PUT | /api/retirements/{item_id} | retirement:edit | 更新退役 |
| DELETE | /api/retirements/{item_id} | retirement:delete | 删除退役 |

### 7.11 校验仪表盘接口（1个）

| 方法 | 路径 | 权限 | 说明 |
|------|------|------|------|
| GET | /api/validation | validation:view | 返回13项校验结果 |

### 7.12 统计概览接口（1个）

| 方法 | 路径 | 权限 | 说明 |
|------|------|------|------|
| GET | /api/stats | dashboard:view | 总资产数/阶段分布/分类分布/维保告警/P1P2未恢复 |

### 7.13 阶段门禁接口（1个）

| 方法 | 路径 | 权限 | 说明 |
|------|------|------|------|
| GET | /api/assets/{asset_code}/stage-gate/{target_stage} | 无 | 检查阶段跳转是否允许 |

### 7.14 下拉选项配置接口（1个）

| 方法 | 路径 | 权限 | 说明 |
|------|------|------|------|
| GET | /api/config/dropdowns | 登录 | 返回所有下拉选项配置 |

### 7.15 导入导出接口（5个）

| 方法 | 路径 | 权限 | 说明 |
|------|------|------|------|
| POST | /api/import/assets | import_export:import | 批量导入资产台账Excel |
| POST | /api/import/{table_type} | import_export:import | 批量导入分表Excel（procurement/change/fault/warranty/retirement） |
| GET | /api/export/assets | import_export:export | 导出资产台账Excel（支持筛选） |
| GET | /api/export/{table_type} | import_export:export | 导出分表Excel |
| GET | /api/template/{table_type} | 无 | 下载导入模板（含示例+提示行） |

**导入逻辑**：
1. 解析Excel表头，映射中文列名→英文字段名
2. 校验下拉选项值是否合法
3. 检查资产编号唯一性（已存在则跳过）
4. 每100行提交一次
5. 返回 `{ success, skipped, errors, total_rows }`

**导出逻辑**：
- 生成openpyxl Workbook，蓝色表头+微软雅黑字体
- 维保过期行整行红色背景，即将到期行黄色背景
- P1/P2故障单元格红色高亮
- 中文文件名使用 `filename*=UTF-8''` + URL编码

### 7.16 报表统计接口（4个）

| 方法 | 路径 | 权限 | 说明 |
|------|------|------|------|
| GET | /api/reports/comprehensive | reports:view | 综合报表 |
| GET | /api/reports/warranty-expiry | reports:view | 维保到期报表（参数days=90） |
| GET | /api/reports/fault-analysis | reports:view | 故障分析报表（参数start_date/end_date） |
| GET | /api/reports/change-frequency | reports:view | 变更频率报表 |

**综合报表包含**：total_assets, by_category, by_stage, by_warranty, warranty_expired_count/list, warranty_expiring_count/list, fault_summary, age_distribution, change_summary, total_purchase_cost

---

## 八、业务规则

### 8.1 阶段门禁规则

合法跳转路径：
```
规划 → [在途, 上架]
在途 → [上架]
上架 → [运行]
运行 → [维修, 待报废]
维修 → [运行, 待报废]
待报废 → [已报废]
```

附加前置条件：
- **跳转到"已报废"**：退役报废表必须有该资产的记录，且 application_no 不为空，data_cleared = "已清除"
- **跳转到"上架"（从在途）**：采购表 inspection_result = "合格"
- **跳转到"运行"（从维修）**：故障表该资产无未恢复记录（recovery_date == None）

### 8.2 13项自动校验

| # | 检查项 | 严重度 | 说明 |
|---|--------|--------|------|
| 1 | 编号空值 | error | 资产编号为空 |
| 2 | SN空值 | warning | SN序列号为空 |
| 3 | 位置空值 | warning | 非报废设备位置为空 |
| 4 | 责任人空值 | error | 上架/运行/维修阶段无责任人 |
| 5 | 阶段空值 | error | 生命周期阶段为空 |
| 6 | 编号重复 | error | 资产编号重复 |
| 7 | 位置重复 | warning | 非报废设备同一位置有多台 |
| 8 | 维保过期 | error | 维保已过期且未续保的运行设备 |
| 9 | 维保即将到期 | warning | 维保30天内到期 |
| 10 | 日期矛盾 | error | 入场日期在未来 |
| 11 | 报废无记录 | error | 已报废但退役表无对应记录 |
| 12 | 孤儿记录 | error | 分表记录关联的编号在主表不存在 |
| 13 | P1/P2未恢复 | error | P1/P2故障未恢复 |

### 8.3 P1/P2故障自动阶段切换
- 创建故障记录时，如果 fault_level 为 P1 或 P2，且资产当前阶段为"运行"，自动将阶段切换为"维修"

### 8.4 采购总价自动计算
- 创建/更新采购记录时，如果有 quantity 和 unit_price，自动计算 total_price = quantity × unit_price

---

## 九、前端设计

### 9.1 技术方案
- **单文件SPA**：所有HTML/CSS/JS在一个 `index.html` 中
- **Vue 3**：CDN加载，使用 Composition API（setup函数）
- **Element Plus**：CDN加载，使用 el-* 组件
- **无构建工具**：直接浏览器运行

### 9.2 页面结构

#### 登录页
- 蓝色渐变背景（`#0052D9 → #003DA6`）
- 居中白色卡片（400px宽，12px圆角，40px内边距）
- 系统Logo图标 + 标题"IT资产全生命周期管理系统" + 副标题"长乐东南数据中心"
- 用户名输入框（User图标）+ 密码输入框（Lock图标，可显示密码）
- 登录按钮（loading状态）
- 底部灰色提示"默认管理员: admin / admin123"

#### 主布局
- **顶部导航栏**：蓝色渐变背景，56px高，左侧标题，右侧用户信息+下拉菜单
  - 用户头像圈（首字大写）+ 用户名 + 下拉（修改密码/退出登录）
- **左侧菜单栏**：200px宽，白色背景，分组+菜单项
  - 数据概览（仪表盘、校验仪表盘）
  - 资产管理（资产台账、采购入库、变更迁移、故障维修、维保续保、退役报废）
  - 数据交换（批量导入、批量导出）
  - 报表统计（综合报表、维保到期、故障分析、变更频率）
  - 系统管理（用户管理、角色管理）— 仅权限用户可见
- **主内容区**：白色卡片，20px内边距

#### 仪表盘页
- 4个统计卡片（网格布局）：总资产数、维保过期、即将到期、P1/P2未恢复
- 下方阶段分布/分类分布展示

#### 数据管理页（6个分表共用模式）
- 顶部筛选栏（搜索框+下拉筛选+操作按钮）
- 数据表格（el-table，支持排序）
- 分页器（el-pagination）
- 新增/编辑对话框（el-dialog + el-form）

#### 用户管理页
- 搜索/状态筛选 + 新增按钮
- 用户表格：用户名、真实姓名、部门、邮箱、手机、状态、角色、操作
- 操作：编辑、重置密码、删除
- 用户表单对话框：用户名、密码（新增时）、真实姓名、部门、邮箱、手机、状态、角色分配（el-select多选）

#### 角色管理页
- 新增按钮
- 角色表格：名称、编码、描述、权限数、用户数、类型（系统/自定义）、操作
- 角色表单对话框：名称、编码、描述、权限配置（按分组展示checkbox）
- 系统角色不可删除，有用户的角色不可删除

### 9.3 前端权限控制

```javascript
// 判断是否有某权限
function hasPerm(perm) {
    if (!currentUser.value?.roles) return false;
    // admin角色拥有所有权限
    if (currentUser.value.roles.some(r => r.code === 'admin')) return true;
    return currentUser.value.permissions?.includes(perm);
}

// 判断是否有任一权限
function hasAnyPerm(...perms) {
    return perms.some(p => hasPerm(p));
}
```

**菜单可见性控制**：
- 系统管理菜单：需要 users:view 或 roles:view
- 各管理页面的增删改按钮：对应 create/edit/delete 权限
- 导入导出菜单：需要 import_export:view

### 9.4 API请求封装
```javascript
const API = '';  // 同源，留空
async function api(path, options = {}) {
    const headers = { 'Content-Type': 'application/json', ...options.headers };
    if (token.value) headers['Authorization'] = `Bearer ${token.value}`;
    const res = await fetch(API + path, { ...options, headers });
    if (res.status === 401) { doLogout(); throw new Error('登录已过期'); }
    if (res.status === 403) throw new Error('权限不足');
    if (!res.ok) { const err = await res.json().catch(() => ({})); throw new Error(err.detail || res.statusText); }
    return res.json();
}
```

### 9.5 Token持久化
- 登录成功后存入 `localStorage`：`asset_token` 和 `asset_user`
- 页面加载时从 localStorage 恢复 token 和用户信息
- 401响应时自动清除并跳转到登录页

---

## 十、启动脚本

`start.py` 应：
1. 将 backend 目录加入 sys.path
2. 导入 main.py 中的 app
3. 打印启动信息（系统名称、数据中心名称、访问地址、API文档地址、默认账号）
4. 运行 `uvicorn.run(app, host="127.0.0.1", port=8000)`

---

## 十一、关键实现注意事项

1. **SQLite外键**：必须在engine连接事件中执行 `PRAGMA foreign_keys=ON`
2. **中文文件名下载**：HTTP头使用 `filename*=UTF-8''` + `urllib.parse.quote()` 编码
3. **数据库迁移**：`Base.metadata.create_all()` 只创建不存在的表，不会修改已有表结构。如果模型变更需要删除旧 .db 文件重新创建
4. **启动初始化**：使用 `@app.on_event("startup")` 调用 `init_default_data()` 创建默认角色和管理员
5. **Pydantic v2**：使用 `model_validate()` 而非 `from_orm()`，使用 `model_dump()` 而非 `dict()`
6. **分表外键**：所有分表通过 `asset_code`（而非id）关联主表 assets
7. **采购总价**：创建和更新时都要自动计算
8. **P1/P2自动切阶段**：创建故障记录时和导入时都要触发
9. **Excel导入列名映射**：中文表头→英文字段名的映射必须准确
10. **前端单文件**：所有CSS在 `<style>` 标签中，所有JS在 `<script>` 标签中，不拆分文件

---

## 十二、验收标准

1. ✅ `python start.py` 可一键启动，访问 http://127.0.0.1:8000 显示登录页
2. ✅ admin/admin123 可正常登录，跳转到仪表盘
3. ✅ 仪表盘显示统计数据，校验仪表盘显示13项检查
4. ✅ 资产台账CRUD正常，阶段变更触发门禁
5. ✅ 5个分表CRUD正常，采购总价自动计算
6. ✅ P1/P2故障自动切换主表阶段为"维修"
7. ✅ 批量导入导出功能正常（Excel文件格式正确）
8. ✅ 4个报表接口返回正确统计
9. ✅ 用户/角色CRUD正常，权限控制生效
10. ✅ viewer角色只能查看，无法创建/删除
11. ✅ 前端菜单/按钮按权限显示/隐藏
12. ✅ Token过期后自动跳转到登录页
