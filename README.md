# IT 资产全生命周期管理系统

> 长乐东南数据中心 · 1618 台设备资产运维体系咨询项目
> 资产编码：`DC-CL-[分类码]-[序号]` ｜ 全生命周期 7 阶段闭环管理

一套面向数据中心 IT 资产运维的**全生命周期管理平台**：覆盖资产从规划、在途、上架、运行、维修、待报废到已报废的完整链路，并提供可后台自助维护的**系统配置中心**、**报表统计看板**、**审批工作流引擎**与**操作审计**。

---

## 功能特性

### 资产全生命周期（7 阶段门禁）
规划 → 在途 → 上架 → 运行 → 维修 → 待报废 → 已报废，每个阶段跳转由「阶段门禁」校验前置条件（如维修→运行需故障记录且全部恢复）。

### 系统配置中心（后台可配置，RBAC：`config:manage`）
配置中心将原本硬编码在代码中的运维规则下沉为数据库配置，使运维主管/管理员可自助维护：

| 阶段 | 配置项 | 说明 |
|------|--------|------|
| **P0** | 字典 / 枚举配置中心 | 下拉枚举、资产分类可后台维护 |
| **P1** | 阶段流转矩阵 | 7 阶段 `valid_transitions` 流转规则可配置（含 `require_*` 前置条件） |
| **P2** | 校验规则开关 | 10 项资产生命周期校验可逐条开启/关闭 |
| **P2** | 聚合白名单 | 报表聚合维度白名单可配置（默认含 11 个字段） |

所有配置均提供「恢复默认」兜底，配置错误不会破坏存量数据。

### 报表统计模块
- 前端基于 **ECharts** 的统计看板：阶段分布、分类构成、可靠性、维保分桶、趋势/对比。
- 后端 `/api/stats/*`：阶段分布、分类构成、可靠性、维保分桶、通用聚合、Overview。

### 审批工作流引擎
数据驱动的审批流解释器（WorkflowTemplate + WorkflowEngine），支持故障降级、移出/报废自动提交、手动指定审批人。

### 操作审计
`audit.py` 记录关键操作日志，便于合规追溯。

### 安全与权限
- JWT + RBAC（约 50 项权限），固定密钥优先从 `.jwt_secret` 读取。
- 生产模式强制要求密钥存在，否则拒绝启动。

---

## 技术栈

| 层 | 技术 |
|----|------|
| 后端 | FastAPI + SQLAlchemy + SQLite（单文件库 `asset_lifecycle.db`） |
| 前端 | Vue 3 + Element Plus（CDN 单文件 SPA `frontend/index.html`，无需打包） |
| 图表 | ECharts（CDN） |
| 测试 | pytest + 自研全量回归脚本 |

---

## 目录结构

```
asset-lifecycle-manager/
├── backend/                 # 后端服务
│   ├── main.py              # FastAPI 应用入口与路由装配
│   ├── database.py          # 数据模型（含配置中心三表）
│   ├── config_api.py        # 配置中心 API（字典/分类/阶段流转/校验开关/聚合白名单）
│   ├── config_cache.py      # 配置缓存 + invalidate_and_rebuild
│   ├── validation.py        # 校验与阶段门禁（读配置表）
│   ├── reports_stats.py     # 报表统计（读聚合白名单）
│   ├── approval.py          # 审批逻辑
│   ├── workflow_engine.py   # 审批流引擎
│   ├── audit.py             # 操作审计
│   ├── seed_*.py            # 幂等种子（字典/工作流/阶段流转/P2配置）
│   └── ...
├── frontend/
│   └── index.html           # 单文件 SPA（含配置中心 5 个 Tab + 统计看板）
├── tests/                   # pytest 测试 + 功能测试
├── scripts/                 # 运维脚本（备份/恢复/健康检查）
├── deploy/                  # 部署：systemd 单元 + GitHub Actions 部署脚本
├── docs/                    # 需求/设计/规格文档
├── deliverables/            # 各模块交付文档与 QA 报告
├── .github/workflows/       # CI/CD (ci-cd.yml)
├── start.py                 # 一键启动（支持 --production/--host/--port）
├── requirements.txt         # 依赖（含 bcrypt==4.0.1 锁定）
└── pytest.ini               # 测试配置
```

---

## 快速开始

### 1. 安装依赖
```bash
python -m pip install -r requirements.txt
```

### 2. 启动服务
```bash
# 开发模式
python start.py

# 生产模式（强制要求 .jwt_secret 或环境变量提供密钥）
python start.py --production --host 0.0.0.0 --port 8000
```
启动后自动建表并执行全部幂等 seed（字典、工作流、阶段流转、P2 配置）。

### 3. 访问
- 前端：http://127.0.0.1:8000 （`frontend/index.html` 由后端托管）
- API 文档：http://127.0.0.1:8000/docs

### 首次管理员
- 账号：`admin`
- 在首次启动前设置 `DEFAULT_ADMIN_PASSWORD=replace-with-a-strong-password`。
- 管理员创建完成后，应从部署环境中移除该变量。

> ⚠️ 公网 IP 的 HTTP 仅用于短期验证，正式对外使用前必须配置 HTTPS。

---

## 测试

```bash
# pytest 套件（生产 MVP / 部署模板）
python -m pytest -q

# 配置模块全量回归（仅限本地隔离实例；脚本会修改测试数据）
# 先阅读参数说明：python qa-test-config-module-P0.py --help

# 冒烟脚本
python smoke_p0.py
python smoke_p1_stage.py
python smoke_p2.py
```

---

## 部署

- **CI/CD**：`.github/workflows/ci-cd.yml` 自动构建与部署。
- **systemd**：`deploy/systemd/` 提供 `asset-lifecycle-backup`（定时备份）与 `asset-lifecycle-healthcheck`（健康检查）单元。
- **备份/恢复**：`scripts/backup_database.py` / `scripts/restore_database.py`。
- 详见 `deploy/README.md` 与 `docs/ci-cd-github-actions.md`。

---

## 文档索引

- 总规格：`SPEC.md`
- 配置模块：`PRD_系统配置模块_P0/P1/P2.md`、`DESIGN_系统配置模块_P1/P2.md`
- 报表统计模块：`PRD_报表统计模块.md` / `_P2.md`、`deliverables/design-report-module*.md`
- 审批工作流：`deliverables/*approval*`
- 交付与 QA 报告：`deliverables/qa-*.md` / `deliverables/qa-test-*.json`

---

## 许可证

本项目内部使用，许可证另行约定。
