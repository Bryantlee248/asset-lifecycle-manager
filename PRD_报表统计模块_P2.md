# 增量 PRD：报表统计模块 P2（联动下钻 + 阶段趋势/对比）

> 文档版本：v0.1（增量版，仅描述变更部分，引用 `PRD_报表统计模块.md` 与 `design-report-module.md`）
> 作者：许清楚（产品经理）
> 日期：2026-07-07
> 关联基础文档：`PRD_报表统计模块.md`（S-12 / S-16 / S-17 / S-18 / S-19 原始定义见 §3）、`deliverables/design-report-module.md`（现有 6 接口、Asset 模型、reports_stats.py 结构、前端 stats tab 结构）

---

## 1. 增量范围（本次 P2 仅做以下三项）

| 编号 | 名称 | 引用基础 PRD | 本轮动作 | 优先级 |
|------|------|--------------|----------|--------|
| S-12 | 图表联动下钻（纯前端） | 原 §3 P1，本次并入 P2 | 点击阶段扇区 / 分类柱条 → 联动过滤其它图表 + 弹出该维度资产明细 | P2-P0 |
| S-16 | 阶段分布趋势（按月折线） | §3 P2 | 新增 `AssetStageLog` + 回填 + `GET /api/stats/stage-trend` | P2-P0 |
| S-17 | 自定义时间范围对比（环比/同比） | §3 P2 | 复用 `AssetStageLog` 快照 + `GET /api/stats/compare` | P2-P0 |

**本轮不做（列入后续，供排期）：**
- S-18 报表订阅（定时推送看板快照）
- S-19 看板布局自定义/收藏（localStorage 持久化）
- S-14 PDF 导出（基础设计中已留按钮占位，本轮不实现）

> 说明：S-12 原在基础 PRD §3 列为 P1，本次并入 P2 一并实现——因其与图表联动基础设施强相关，且与 S-16/S-17 共用「阶段筛选状态」与 `AssetStageLog` 数据底座，拆分反而增加联调成本。

---

## 2. 核心数据方案决策（最重要，给架构师的明确指引）

### 2.1 问题确认

当前 `Asset` 仅存 `lifecycle_stage`（当前阶段），**无任何阶段变更历史时间线**。趋势（S-16）与时间对比（S-17）都依赖「某资产在历史上某月处于某阶段」的快照。必须新增历史数据源。

### 2.2 方案对比与推荐

| 方案 | 思路 | 优点 | 缺点 | 结论 |
|------|------|------|------|------|
| **A（推荐）** | 新增事件日志表 `AssetStageLog`，在阶段变更入口写入；对现有资产按已知日期字段**推演回填** | 追加式、写入成本低；既支撑按月快照（趋势），也支撑「A→B 区间发生了哪些变更」（对比）；可下钻到单资产变更明细 | 回填为推演值（非真实事件），需明确标注 | ✅ 采用 |
| B（备选） | 不建事件表，改为每月定时落「阶段快照表 `StageSnapshot(month, stage, count)`」 | 查询极简（直接读快照） | 丢失事件级粒度；无法回答「本月相对上月哪些资产发生了阶段变化」；历史月份在接入前为空、仍需回填空窗 | ❌ 不采用 |

**推荐方案 A。** 理由：趋势与对比本质是「事件在数轴上的投影」，事件日志是唯一能同时服务两者且支持明细下钻的底座；写入点为既有代码中的有限几处（见 2.4），改造面可控。

### 2.3 新增数据模型：`AssetStageLog`

> 位置建议：`backend/database.py` 新增类；迁移脚本 `backend/migrate_stage_log.py`（ALTER + 回填，沿用 `migrate_original_value.py` 的 `backup_database` 模式）。

| 字段 | 类型 | 说明 |
|------|------|------|
| id | Integer PK | 自增 |
| asset_code | String(30) | 关联资产编号（FK assets.asset_code） |
| from_stage | String(20) | 变更前阶段；资产「出生」记录 from_stage 记为 `规划` 或空串 |
| to_stage | String(20) | 变更后阶段 |
| changed_at | Date | 变更发生日期（回填用推演日期，前向用真实日期） |
| operator | String(30) | 操作人（前向取 current_user.real_name / 审批 applicant；回填记为 `system_backfill`） |
| reason | String(200) | 变更原因（审批类型 / 故障单号 / 回填标记等） |
| is_backfill | Boolean default=False | **是否为回填推演值**（前端/对比接口据此标注口径） |

> 7 阶段顺序（来自 `constants.LIFECYCLE_STAGES`）：规划 < 在途 < 上架 < 运行 < 维修 < 待报废 < 已报废。

### 2.4 写入入口（明确指引，避免漏写）

| # | 入口 | 文件:行 | 触发场景 | 推荐写入方式 |
|---|------|---------|----------|--------------|
| 1 | `drive_stage_change()` | `approval.py:185` | 全部**审批驱动**变更（手动阶段变更、故障降级→维修、移出报废→待报废） | **主入口**。在 `asset.lifecycle_stage = request.target_stage` 处同时 `db.add(AssetStageLog(from_stage=request.current_stage, to_stage=request.target_stage, changed_at=request.approved_at.date(), operator=applicant, reason=type_name, is_backfill=False))`。注意：用 `request.current_stage`（审批记录的原始阶段）而非 `asset.lifecycle_stage`（彼时已是被改后的值），避免故障降级路径记录「维修→维修」空转 |
| 2 | `create_fault()` | `main.py:1159` | P1/P2-严重故障**直接置 维修**后触发自动审批 | 此处已直接 `asset.lifecycle_stage="维修"`，`drive_stage_change` 会记录「维修→维修」空转。故**在此处补写**：`from_stage=original_stage, to_stage="维修", reason=f"P{level}故障自动降级 故障单{item.id}", is_backfill=False` |
| 3 | 故障 Excel 导入 | `import_export_reports.py:289` | 导入 P1/P2-严重故障行时直接置 维修 | 同 #2 逻辑，补写一条 `from_stage=原阶段, to_stage="维修", reason="Excel导入故障降级", is_backfill=False` |
| 4 | 资产建台账（出生） | `main.py:888/948` | 入库建资产初始阶段（默认 上架） | **可选**：写入 `from_stage="规划", to_stage=初始阶段, changed_at=entry_date, reason="资产建档", is_backfill=False`，使时间线有起点。不强求，但建议做以保证快照完整 |

> 建议封装辅助函数 `record_stage_change(db, asset_code, from_stage, to_stage, changed_at, operator, reason, is_backfill=False)`（置于 `reports_stats.py` 或新建 `stage_log.py`），上述入口统一调用，减少重复与遗漏。现有 `AuditLog`（approval.py:198）保留不动，二者职责不同（审计 vs 阶段时间线）。

### 2.5 历史回填口径（推演值，明确标注）

> 对现有约 100 台资产，用已有日期字段推演出一条「合理」阶段时间线写入 `AssetStageLog`，使趋势图/对比图**立即可见**。回填结果不代表真实历史事件，仅用于演示与分析。

**回填算法（逐资产）：**

| 步骤 | 锚点事件（date, stage） | 数据来源 |
|------|------------------------|----------|
| 0 | 出生：`(entry_date, 上架)`；若 `entry_date` 为空则用 `AssetInbound.inbound_date`，再空则 `规划` 置于一个很早的兜底日期 | `Asset.entry_date` / `AssetInbound.inbound_date` |
| 1 | 故障期：`(fault_date, 维修)`；若有 `recovery_date` 且 ≥ `fault_date`，追加 `(recovery_date, 运行)` | `Fault.fault_date` / `Fault.recovery_date` |
| 2 | 待报废：`(Retirement.approval_date, 待报废)`（若 `approval_date` 为空则用 `uninstall_date`） | `Retirement.approval_date` / `uninstall_date` |
| 3 | 已报废：`(Retirement.uninstall_date, 已报废)`；若该资产有 `AssetOutbound.outbound_date` 且无已报废记录，则 `(outbound_date, 已报废)` | `Retirement.uninstall_date` / `AssetOutbound.outbound_date` |

**处理规则：**
- 按日期升序排列锚点；**强制单调不回退**：若某事件会使阶段顺序倒退（如 recovery 早于 fault、outbound 早于 entry），则夹断到当前已达阶段（取 7 阶段顺序的较大值）。
- 同一日期多条锚点取「最靠后阶段」。
- 所有回填记录 `is_backfill=True`，`operator="system_backfill"`，`reason="历史推演回填"`。
- 若资产当前 `lifecycle_stage` 与最后锚点阶段不一致，以当前阶段为最终态补一条收尾记录（保证「现在」与时间线末端一致）。

**趋势图时间粒度与口径：**
- 粒度：**按月**。X 轴 = 每月末（如 `2025-08-31`）。范围：从 `min(entry_date)` 所在月初 到 当前月（默认最近 12 个月，可 `?months=N` 调整）。
- **每月末快照** = 对每个资产取「日期 ≤ 该月月末的最后一条锚点阶段」；跨月未变则沿用。统计各阶段资产数（7 条折线，Σ=总资产数，含已报废）。
- 首页标注：「历史数据为推演回填值，真实事件自接入日起记录」。

**环比/同比对比对象（S-17）：**
- 选择两个时间窗口 `range_a`、`range_b`（各为一个月份或月份区间），对比两者**月末快照**的差异：
  - **环比**：`range_b`=当月，`range_a`=上一月。
  - **同比**：`range_b`=当月，`range_a`=去年同月。
- 对比指标（metric）：`stage`（各阶段数量）、`total_assets`、`active_assets`（ACTIVE_STAGES 合计）、`original_value`（原值合计）、`fault_count`（该窗口故障数）。返回两窗口快照 + 变化量(Δ) + 变化率(%)。

---

## 3. S-12 联动下钻交互定义（纯前端）

> 复用基础设计 §3.5 前端 `StatsView` 与现有图表容器（chart-stage / chart-category / chart-reliability / chart-warranty / chart-aggregate）及 `buildXxxOption()` / `renderChart()`。新增点击监听与「联动筛选状态」。

### 3.1 联动规则

| 触发 | 点击对象 | 联动行为 | 明细弹窗 |
|------|----------|----------|----------|
| 阶段环形图 | 某阶段扇区（`chart-stage` 的 `chart.on('click')`，`params.name`=阶段名） | 置 `selectedStage`：重新请求 `reliability`（按阶段过滤 `by_stage_failure_rate`）、`warranty-buckets`（仅该阶段）、`aggregate`（字段=lifecycle_stage 时锁定该值）；相关图表刷新 | 弹 Drawer/Dialog，复用 `GET /api/assets?lifecycle_stage=<阶段>` 列出该阶段资产清单（分页、可排序） |
| 分类柱状图 | 某分类柱条（`chart-category`，`params.name`=分类中文名） | 置 `selectedCategory`：重新请求 `category-composition?category=<分类>` 展示该分类下型号构成；aggregate 字段=asset_category 时锁定该值 | 弹 Drawer，复用 `GET /api/assets?asset_category=<分类>` 列出该分类资产清单 |

### 3.2 实现要点（给工程师）
- 在 `renderCharts()` 对 `chart-stage`、`chart-category` 调用 `chart.on('click', handler)` 绑定（注意 `disposeCharts()` 后重绑，避免重复绑定——可在 `renderChart` 初始化时绑定一次）。
- 联动状态用 `reactive` ref（`selectedStage` / `selectedCategory`），`loadStats()` 与 `onAggregateChange()` 透传这些参数到对应接口。
- 提供「清除筛选」按钮（或再次点击已选扇区取消），恢复全量请求；避免联动死循环（点击触发的刷新不再二次触发点击）。
- 明细弹窗**复用现有 `GET /api/assets`**（基础架构 §6 确认其支持 `lifecycle_stage`/`asset_category` 过滤，见 `main.py:634`），不新增后端接口。

> 验收：点击阶段扇区后，可靠性/维保/聚合图按该阶段刷新且无死循环；点击分类柱条后型号构成与明细按该分类刷新；弹窗清单数据与 `/api/assets` 过滤结果一致。

---

## 4. S-16 / S-17 接口需求（增量 2 个接口，复用 reports:view）

> 在基础设计 §3.3 的 6 个聚合函数基础上**新增 2 个**：`get_stage_trend(db, months)`、`get_stage_compare(db, range_a, range_b, metric)`。路由挂同一 `stats_router`（前缀 `/api/stats`）。字段名以下为建议，最终由架构师定稿。

### 4.1 阶段分布趋势 `GET /api/stats/stage-trend`

| 项 | 说明 |
|----|------|
| 入参 | `months`(int, 默认 12，范围 1~60)：返回最近 N 个月月末快照 |
| 权限 | `reports:view`（沿用） |
| 建议返回 | `{ "months": ["2025-08","2025-09",...], "stages": ["规划","在途","上架","运行","维修","待报废","已报废"], "matrix": [ { "month":"2025-08", "counts":{ "规划":0,"在途":1,"上架":40,... }, "total":100 }, ... ], "is_backfill": true }` |
| 口径 | counts 为每月末各阶段资产数（同 §2.5）；`is_backfill` 标示是否含回填推演值 |
| 前端 | 在「生命周期阶段分布」卡片下新增一个「按月趋势」折线区（或独立卡片），7 条折线（ECharts line），X 轴=months |

### 4.2 时间范围对比 `GET /api/stats/compare`

| 项 | 说明 |
|----|------|
| 入参 | `range_a`(YYYY-MM)、`range_b`(YYYY-MM)、`metric`(stage\|total_assets\|active_assets\|original_value\|fault_count，默认 stage) |
| 权限 | `reports:view`（沿用） |
| 建议返回 | `{ "metric":"stage", "a":{ "month":"2025-07","snapshot":{...各阶段数/指标值} }, "b":{ "month":"2025-08","snapshot":{...} }, "delta":{ "规划":0,"上架":-3,... }, "delta_pct":{ "上架":-7.5,... }, "compare_type":"环比" }`（`compare_type` 由前端据 range_a/range_b 推导或显式传参） |
| 口径 | snapshot = 该范围月末快照（取 `range_x` 月最后一日）；metric≠stage 时 snapshot 为单值 |
| 前端 | 「阶段分布趋势」卡片旁新增「对比」控件：两个月份选择器 + 指标选择 + 展示变化量/率（表格或柱状对比） |

---

## 5. 需求池（增量 P0 / P1，可验收条目）

| 编号 | 描述 | 优先级 | 验收标准 |
|------|------|--------|----------|
| P2-01 | **新增 `AssetStageLog` 模型 + 迁移脚本**（建表 + 索引 asset_code/changed_at） | P0 | `Base.metadata.create_all` 后表存在；迁移脚本可重复安全执行（先 `backup_database`，幂等） |
| P2-02 | **阶段变更写入日志**：`drive_stage_change`、create_fault、故障导入、资产建档 4 处统一调用 `record_stage_change`（见 §2.4） | P0 | 此后每次审批阶段变更 / P1P2 故障降级 / 故障导入，均产生一条 `is_backfill=False` 的 `AssetStageLog`（from→to 正确，无「维修→维修」空转） |
| P2-03 | **历史回填脚本**：对约 100 台现有资产按 §2.5 推演时间线并写入 `AssetStageLog(is_backfill=True)` | P0 | 回填后：每月末 Σcounts = 总资产数（100）；每台资产时间线单调不回退；末态 = 当前 `lifecycle_stage`；回填记录 `is_backfill=True` |
| P2-04 | **`GET /api/stats/stage-trend?months=N`**：返回按月各阶段数量矩阵 | P0 | 默认 12 个月；返回 months/stages/matrix；含 `is_backfill` 标记；无 `reports:view` → 403；非法 months → 400（或夹断到 [1,60]） |
| P2-05 | **`GET /api/stats/compare?range_a=&range_b=&metric=`**：返回两窗口快照 + Δ + Δ% | P0 | 返回 a/b/delta/delta_pct（metric=stage 时按阶段；其余为单值）；compare_type 正确；无权限 → 403 |
| P2-06 | **S-12 联动下钻**：阶段扇区/分类柱条点击联动过滤 + 明细弹窗（复用 `/api/assets`） | P0 | 点击后关联图表刷新、弹窗清单与 `/api/assets` 过滤一致；有「清除筛选」；无死循环 |
| P2-07 | **趋势/对比前端渲染**：阶段分布卡片下新增按月趋势折线 + 对比控件 | P1 | 折线随 `stage-trend` 正确渲染；对比控件选择两月 + 指标后展示 Δ/Δ% |
| P2-08 | **回填口径标注**：看板/导出/对比结果明确「历史为推演值，真实事件自接入日起记录」 | P1 | 趋势图区与对比结果含口径说明文字；`is_backfill` 在前端可识别并提示 |
| P2-09 | **回归**：新增 2 接口不破坏现有 7 接口与既有报表 | P0 | 既有 `qa-test-report-module.py`（12/12）全过；新增接口补测试（trend 长度/Σ、compare delta 计算正确） |

---

## 6. 待确认问题（需主理人/用户拍板）

1. **回填推演值是否可接受？** 趋势/对比图在接入前的历史数据是**按已知日期字段推演**的（非真实事件）。是否接受以推演值驱动趋势/对比展示（明确标注口径），还是希望趋势图仅在「有真实 `AssetStageLog` 之后」才开始累积、接入前留空？（推荐：接受推演回填，标注口径，立即可见价值。）
2. **联动是否弹明细列表？** S-12 建议点击扇区/柱条**既联动过滤其它图表，又弹出该维度资产明细**（复用 `/api/assets`）。是否两者都要，还是仅做图表联动、明细列表放到后续？（推荐：两者都要，下钻体验更完整。）
3. **对比默认指标与入口位置？** `compare` 默认 `metric=stage`（各阶段数量变化）是否符合预期？对比控件放在「阶段分布趋势」卡片内联合展示，还是独立卡片？环比/同比是否由用户手动选两月，还是提供「环比/同比」快捷按钮自动算？（推荐：默认 stage + 快捷环比/同比按钮 + 手动选月兜底。）

---

## 附：与基础设计的衔接点（供架构师快速定位）

- 新增 2 接口挂载于 `backend/reports_stats.py` 的 `stats_router`（`design-report-module.md` §3.3），`main.py` 无需改挂载逻辑。
- 新增 `AssetStageLog` 模型 + `migrate_stage_log.py`，类比 `database.py` 的 `original_value` 列 + `migrate_original_value.py`（§3.1 / §3.4）。
- 前端改动限于 `frontend/index.html` 的 stats tab（`design-report-module.md` §3.5），新增趋势折线区、对比控件、点击监听、`selectedStage/selectedCategory` 联动状态；图表容器 id 与 `buildXxxOption`/`renderChart` 沿用。
- 权限、错误码、ECharts 生命周期（init/resize/dispose）全部沿用基础设计 §7 约定，不新增权限项。
- **回归基线**：`deliverables/qa-test-report-module.py` 现有 12/12（100 资产、total_original_value≈19,560,662.48、total_faults=33），P2 不得破坏；并补充 trend/compare 用例。
