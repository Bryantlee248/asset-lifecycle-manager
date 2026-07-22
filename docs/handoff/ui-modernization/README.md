# 全系统 UI 现代化改造：外部 AI 交接包

本目录用于将“IT 资产全生命周期管理系统”全系统页面现代化改造交给外部 AI 平台执行。开发前必须完整阅读以下文件，顺序不得省略：

1. 项目根目录 `AGENTS.md`：协作、安全、Git、QA 与部署红线。
2. `docs/superpowers/specs/2026-07-21-full-system-ui-modernization-design.md`：已确认的设计规格。
3. `PRD.md`：业务目标、范围与验收目标。
4. `PAGE-MAPPING.md`：现有页面到新导航、页面模式的逐项映射。
5. `TECHNICAL-SPEC.md`：实现约束、保留项、测试要求与文件边界。
6. `ACCEPTANCE-CHECKLIST.md`：逐项验收标准。
7. `docs/superpowers/plans/2026-07-21-full-system-ui-modernization.md`：实施批次与任务顺序。

## 项目事实

- 项目根目录：`D:\Codex Project\Report-Modified\asset-lifecycle-manager`。
- 前端为单文件 Vue 3 SPA：`frontend/index.html`，使用 Element Plus、ECharts 和 CDN；目前没有构建工具链。
- 后端为 FastAPI + SQLAlchemy + SQLite。此次任务是前端展示和交互重构，默认不修改后端接口、数据模型、权限、数据库或部署文件。
- 当前工作区包含其他人尚未提交的恢复改动与报告文件。只允许增量修改，不得清理、重置、覆盖或提交他人文件。

## 非目标

- 不新增业务模块，不改变资产生命周期 7 阶段、阶段门禁、审批流、RBAC 权限或 API 契约。
- 不将前端迁移到 React、Vite、TypeScript、Tailwind 或其他新框架。
- 不部署、不推送、不访问远端或公网环境，不执行可能写入现有实例数据的 QA 脚本。

## 交付物

- 已更新的 `frontend/index.html`。
- 与公共导航、标签页、响应式规则相匹配的静态契约测试。
- 完整测试与浏览器验证记录。
- 修改说明：实际文件、行为变化、验证证据、已知限制；默认保持未提交。
