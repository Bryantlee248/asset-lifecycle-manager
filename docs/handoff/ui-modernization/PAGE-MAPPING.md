# 现有页面到新信息架构映射

实现必须保留右侧 `currentTab` 值；左侧为新导航分组和显示名称。

| 新一级域 | 新显示名称 | `currentTab` | 统一页面模式 | 核心保留行为 |
| --- | --- | --- | --- | --- |
| 工作台 | 运营总览 | `dashboard` | 运营总览 | 原统计、快捷入口与加载逻辑 |
| 工作台 | 校验与风险 | `validation` | 运营总览 | 原校验项目、数量和跳转 |
| 资产运营 | 资产台账 | `assets` | 台账列表 + 详情/表单 | 资产 CRUD、筛选、导入导出关联 |
| 资产运营 | 采购管理 | `procurement` | 台账列表 + 详情/表单 | 采购记录与审批字段 |
| 资产运营 | 入库管理 | `inbound` | 台账列表 + 详情/表单 | `inbound:view` 权限 |
| 资产运营 | 出库管理 | `outbound` | 台账列表 + 详情/表单 | `outbound:view` 权限 |
| 资产运营 | 变更管理 | `changes` | 台账列表 + 详情/表单 | 变更记录和审批信息 |
| 资产运营 | 故障与维修 | `faults` | 台账列表 + 详情/时间线 | 故障恢复与阶段门禁关联 |
| 资产运营 | 维保管理 | `warranties` | 台账列表 + 详情/时间线 | 到期状态和提醒语义 |
| 资产运营 | 退役与报废 | `retirements` | 台账列表 + 详情/审批 | 报废移出自动提交审批 |
| 协同中心 | 审批中心 | `approval` | 审批待办 + 详情 | `approval:view`、全部子标签与审批操作 |
| 协同中心 | 审批通知 | `approvalNotify` | 通知列表 | `loadApprovalNotifications()`、未读数 |
| 协同中心 | 导入与导出 | `importExport` | 工具页 | 所有导入导出选项与筛选字段 |
| 洞察报告 | 运营报表 | `reports` | 报表页 | 原报表权限、图表和导出 |
| 洞察报告 | 统计看板 | `stats` | 运营总览 | `reports:view` 权限与 ECharts 数据 |
| 系统治理 | 用户管理 | `users` | 配置与管理 | `users:view` 权限、用户 CRUD |
| 系统治理 | 角色与权限 | `roles` | 配置与管理 | `roles:view` 权限、权限分组 |
| 系统治理 | 配置中心 | `config` | 配置与管理 | `config:manage`、`loadConfig()`、所有配置子标签 |

## 标签页约束

- `config`：保留现有 `configSubTab`、`configDomain`、`onConfigSubTabChange`、`onConfigDomainChange` 和全部配置项目。
- `approval`：保留 `approvalSubTab`、全部审批筛选、创建/撤回/通过/驳回/重新提交/详情动作。
- 报表、统计等模块若已有页内切换，必须保持现有数据加载调用时机。
