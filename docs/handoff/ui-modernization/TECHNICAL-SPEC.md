# 技术实施规格与保护边界

## 1. 允许修改的主要文件

- 主实现：`frontend/index.html`。
- 必要时更新：`tests/test_production_mvp.py`，仅用于维护或新增前端静态契约测试。
- 必要时更新：与前端行为直接相关的已有测试文件。
- 本次 UI 任务默认不得修改 `backend/`、数据库、部署模板、CI、QA 脚本或生产配置。

## 2. 前端技术边界

- 保持 Vue `3.5.13`、Element Plus `2.9.1`、`@element-plus/icons-vue@2.3.1`、ECharts `5.5.0` 的 CDN 模式。
- 保持所有 API 调用、响应字段处理、`ref` 名称、`currentTab`、权限方法、数据加载方法和对话框状态变量可用。
- 使用已经注册的 Element Plus 图标；不得新增重复 CDN、未注册图标库、构建步骤或新的全局依赖。
- 登录页也属于本次视觉范围，但不得改变认证流程、输入字段、错误提示来源或默认账号策略。

## 3. 现有静态契约测试必须同步维护

`tests/test_production_mvp.py::test_frontend_uses_the_modern_operations_console_system` 当前验证以下运行时契约：

- CSS token：`--surface`、`--shell`、`--accent`、`--healthy`、`--warning`、`--critical`。
- 选择器：`.app-header`、`.sidebar`、`.page-card`、`.filter-bar`、`.login-header .login-logo`、`.el-tabs__item.is-active`、`.el-dialog__footer`、`@media (max-width: 900px)`。
- 不得使用 `linear-gradient`。
- Vue 必须先于 Element Plus 图标加载；图标 IIFE 和 `Object.entries(ElementPlusIconsVue)` 必须保留；`<el-icon>` 至少 18 个。

若重构确需改变选择器或视觉 token，必须先调整该测试使其验证同等或更强的契约，再改动页面；不得删除断言来制造通过。

## 4. 实现规则

- 只在既有 `style` 块内增量定义视觉 token 和公共样式；避免无关格式化或重排整个 4000+ 行文件。
- 新增通用类前先检索同类样式，优先复用 `.page-card`、`.filter-bar`、`.stat-cards`、`.stage-tag`、审批状态类、Element Plus 组件变量。
- 通过现有方法切换页面，不能将 `currentTab='assets'` 等逻辑改为新值。
- 所有状态信息同时使用文字和颜色；高风险/危险操作保留既有确认弹窗。
- 窄屏处理采用：导航抽屉或文字菜单、筛选纵向排列、表格字段优先级/详情入口、全宽弹窗；不得仅缩小字体。

## 5. 数据和安全约束

- 仅用浏览器本地模拟数据或隔离数据库验证；不得将 `127.0.0.1:8000` 作为 QA 默认目标。
- 不得运行 `qa-test-config-module-P0.py`、`P1.py`、`P2.py`，除非用户明确允许并提供显式本地目标、`--destructive` 和隔离数据库。
- 不得登录公网地址、远端服务器或真实生产环境。

## 6. 必须执行的验证

```powershell
python -m pytest -q --disable-warnings
python -m compileall backend -q
git diff --check
```

另需以隔离本地实例进行浏览器验收：登录、每个一级导航入口、资产 CRUD、阶段流转、审批、配置中心、统计图表、桌面 1440px、平板 768px、手机 375px。
