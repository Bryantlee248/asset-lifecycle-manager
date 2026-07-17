# Modern Operations Console Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Modernize every existing UI tab into a consistent operational console without changing backend behavior, API calls, permissions, tab keys, or data fields.

**Architecture:** Keep the application as the current single-file Vue + Element Plus page. Add a small visual-contract test, then refactor the existing CSS into design tokens and scoped component overrides; make only targeted template edits for navigation icons and existing page headers. All existing Vue refs, methods, API calls, and `currentTab` values remain unchanged.

**Tech Stack:** Static HTML, Vue global build, Element Plus CDN, Element Plus Icons Vue CDN, pytest, existing `start.py` server.

---

## File Structure

- Modify: `frontend/index.html` - visual tokens, common layout rules, icon registration, navigation markup, and responsive behavior.
- Modify: `tests/test_production_mvp.py` - front-end visual-contract test collected by the existing default pytest configuration.
- Create: `docs/superpowers/specs/2026-07-17-modern-operations-console-design.md` - approved visual scope.
- Create: `docs/superpowers/plans/2026-07-17-modern-operations-console.md` - this implementation plan.

### Task 1: Establish the visual contract

**Files:**

- Modify: `tests/test_production_mvp.py`

- [ ] **Step 1: Write the failing front-end visual-contract test**

Append this test after `test_release_files_do_not_publish_a_default_admin_password`:

```python
def test_frontend_uses_the_modern_operations_console_system():
    html = (PROJECT_ROOT / "frontend" / "index.html").read_text(encoding="utf-8")

    required_tokens = (
        "--surface:",
        "--shell:",
        "--accent:",
        "--healthy:",
        "--warning:",
        "--critical:",
    )
    required_selectors = (
        ".app-header { background: var(--surface);",
        ".sidebar { background: var(--shell);",
        ".page-card { background: var(--surface);",
        ".filter-bar {",
        ".el-tabs__item.is-active",
        ".el-dialog__footer",
        "@media (max-width: 900px)",
    )

    assert all(token in html for token in required_tokens)
    assert all(selector in html for selector in required_selectors)
    assert "linear-gradient" not in html
    assert "ElementPlusIconsVue" in html
```

- [ ] **Step 2: Run the test to verify RED**

Run:

```powershell
python -m pytest tests/test_production_mvp.py::test_frontend_uses_the_modern_operations_console_system -q
```

Expected: fail because the current page has no `--surface` token, uses two gradients, and does not register Element Plus icon components.

### Task 2: Rebuild the shared console shell and data surfaces

**Files:**

- Modify: `frontend/index.html:8-112`

- [ ] **Step 1: Replace the current root token and shell rules**

Replace the existing `:root`, `.app-header`, `.app-body`, `.sidebar`, `.main-content`, `.stat-card`, `.page-card`, and `.filter-bar` rules with this shared system. Keep all existing class names so no Vue template behavior changes.

```css
:root {
    --surface: #ffffff;
    --shell: #202b36;
    --canvas: #f5f7fa;
    --line: #dde3ea;
    --text: #1f2933;
    --muted: #667085;
    --accent: #2563eb;
    --accent-soft: #eaf1ff;
    --healthy: #0f766e;
    --healthy-soft: #e6f5f2;
    --warning: #b45309;
    --warning-soft: #fff5e6;
    --critical: #c2413b;
    --critical-soft: #fff0ee;
}

body { background: var(--canvas); color: var(--text); }
.app-header {
    background: var(--surface);
    color: var(--text);
    height: 56px;
    padding: 0 24px;
    border-bottom: 1px solid var(--line);
    box-shadow: none;
}
.app-header h1 { font-size: 16px; font-weight: 650; letter-spacing: 0; }
.app-header .header-right { color: var(--muted); opacity: 1; }
.sidebar { width: 216px; background: var(--shell); border-right: 0; }
.sidebar .menu-group { padding: 10px 0; }
.sidebar .menu-group-title { color: #9dabb9; padding: 8px 16px; letter-spacing: .08em; }
.sidebar .menu-item { color: #d4dde7; margin: 2px 8px; padding: 10px 12px; border-left: 0; border-radius: 4px; }
.sidebar .menu-item:hover { background: #2c3b4b; color: #ffffff; }
.sidebar .menu-item.active { background: #334a62; color: #ffffff; font-weight: 600; }
.sidebar .menu-item .icon { display: inline-flex; width: 20px; margin-right: 10px; justify-content: center; }
.main-content { margin-left: 216px; padding: 24px; }
.stat-cards { gap: 12px; margin-bottom: 16px; }
.stat-card, .page-card {
    background: var(--surface);
    border: 1px solid var(--line);
    border-radius: 6px;
    box-shadow: none;
}
.stat-card { min-height: 116px; padding: 16px; }
.stat-card .label, .stat-card .sub { color: var(--muted); }
.stat-card .value { color: var(--text); }
.stat-card .value.success { color: var(--healthy); }
.stat-card .value.warning { color: var(--warning); }
.stat-card .value.danger { color: var(--critical); }
.page-card { padding: 20px; margin-bottom: 16px; }
.page-card .card-header { margin-bottom: 14px; }
.page-card .card-title { font-size: 15px; }
.filter-bar {
    min-height: 40px;
    gap: 8px;
    margin-bottom: 14px;
    padding: 10px 12px;
    background: #f8fafc;
    border: 1px solid var(--line);
    border-radius: 6px;
}
```

- [ ] **Step 2: Replace gradient login styling with the same visual system**

Replace the current `.login-container` and `.login-card` rules with:

```css
.login-container { min-height: 100vh; display: grid; place-items: center; background: var(--canvas); }
.login-card { width: min(400px, calc(100vw - 32px)); padding: 32px; background: var(--surface); border: 1px solid var(--line); border-radius: 6px; box-shadow: 0 16px 36px rgba(31, 41, 51, .10); }
.login-header .login-logo { color: var(--accent); font-size: 36px; }
```

- [ ] **Step 3: Run the visual-contract test to verify GREEN**

Run:

```powershell
python -m pytest tests/test_production_mvp.py::test_frontend_uses_the_modern_operations_console_system -q
```

Expected: pass once the shell tokens, gradient removal, and the remaining required selectors are in place.

### Task 3: Standardize tables, sub-tabs, status tags, forms, and dialogs

**Files:**

- Modify: `frontend/index.html:77-112`

- [ ] **Step 1: Add one Element Plus component override block**

Append this CSS immediately before the existing media queries:

```css
.el-table { --el-table-border-color: var(--line); --el-table-header-bg-color: #f8fafc; --el-table-row-hover-bg-color: #f4f8ff; color: var(--text); }
.el-table th.el-table__cell { color: #475467; font-size: 12px; font-weight: 650; }
.el-table .cell { font-size: 13px; line-height: 20px; }
.el-button--primary { --el-button-bg-color: var(--accent); --el-button-border-color: var(--accent); --el-button-hover-bg-color: #1d4ed8; --el-button-hover-border-color: #1d4ed8; }
.el-tabs__header { margin: 0 0 16px; }
.el-tabs__item { height: 38px; color: var(--muted); font-weight: 500; }
.el-tabs__item.is-active { color: var(--accent); font-weight: 650; }
.el-tabs__active-bar { height: 2px; background: var(--accent); }
.el-tag { border-radius: 4px; font-weight: 600; }
.stage-tag, .approval-status-tag { border-radius: 4px; font-weight: 600; }
.el-dialog, .el-drawer { border-radius: 6px; }
.el-dialog__header, .el-drawer__header { margin: 0; padding: 18px 20px; border-bottom: 1px solid var(--line); }
.el-dialog__body, .el-drawer__body { padding: 20px; }
.el-dialog__footer { display: flex; justify-content: flex-end; gap: 8px; padding: 14px 20px; border-top: 1px solid var(--line); }
.el-form-item__label { color: #475467; font-weight: 600; }
```

- [ ] **Step 2: Add responsive rules for the existing shell and list tabs**

Append:

```css
@media (max-width: 1200px) { .stat-cards { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
@media (max-width: 900px) {
    .app-header { padding: 0 16px; }
    .app-header .header-right > span:not(:last-child) { display: none; }
    .sidebar { width: 64px; }
    .sidebar .menu-group-title, .sidebar .menu-item > :not(.icon) { display: none; }
    .sidebar .menu-item { justify-content: center; margin: 4px 8px; padding: 10px; }
    .sidebar .menu-item .icon { margin: 0; }
    .main-content { margin-left: 64px; padding: 16px; }
    .filter-bar { align-items: stretch; }
    .filter-bar .el-input, .filter-bar .el-select { width: 100% !important; }
}
@media (max-width: 640px) {
    .stat-cards { grid-template-columns: 1fr; }
    .main-content { padding: 12px; }
    .page-card { padding: 14px; }
    .el-dialog { width: calc(100vw - 24px) !important; }
}
```

- [ ] **Step 3: Run the visual-contract test and the default regression suite**

Run:

```powershell
python -m pytest tests/test_production_mvp.py::test_frontend_uses_the_modern_operations_console_system -q
python -m pytest -q
```

Expected: visual contract passes and the default regression suite remains green.

### Task 4: Replace navigation decoration with real icons and verify behavior

**Files:**

- Modify: `frontend/index.html:8-12`
- Modify: `frontend/index.html:200-253`
- Modify: `frontend/index.html:3350-3352`

- [ ] **Step 1: Extend the visual-contract test for icon registration**

Add these assertions inside `test_frontend_uses_the_modern_operations_console_system`:

```python
assert "@element-plus/icons-vue@2.3.1/dist/index.iife.min.js" in html
assert "Object.entries(ElementPlusIconsVue)" in html
assert html.count("<el-icon>") >= 18
```

- [ ] **Step 2: Run the test to verify RED**

Run:

```powershell
python -m pytest tests/test_production_mvp.py::test_frontend_uses_the_modern_operations_console_system -q
```

Expected: fail because the page currently loads only the icon stylesheet and the menu contains emoji characters.

- [ ] **Step 3: Load and register the existing Element Plus icon package**

Add the following script tag directly after the existing Element Plus icon stylesheet link:

```html
<script src="https://unpkg.com/@element-plus/icons-vue@2.3.1/dist/index.iife.min.js"></script>
```

Register all icon components directly before `app.use(ElementPlus);`:

```javascript
Object.entries(ElementPlusIconsVue).forEach(([name, component]) => {
    app.component(name, component);
});
```

- [ ] **Step 4: Replace the menu icon spans without changing their click handlers or `currentTab` values**

Use the following component substitutions inside the existing `.menu-item` elements:

```html
<span class="icon"><el-icon><Odometer /></el-icon></span>
<span class="icon"><el-icon><CircleCheck /></el-icon></span>
<span class="icon"><el-icon><Files /></el-icon></span>
<span class="icon"><el-icon><DataAnalysis /></el-icon></span>
<span class="icon"><el-icon><Box /></el-icon></span>
<span class="icon"><el-icon><ShoppingCart /></el-icon></span>
<span class="icon"><el-icon><Switch /></el-icon></span>
<span class="icon"><el-icon><WarningFilled /></el-icon></span>
<span class="icon"><el-icon><User /></el-icon></span>
<span class="icon"><el-icon><Setting /></el-icon></span>
```

Use this exact mapping for each existing `currentTab` row. Keep each row's `v-if`, `@click`, and tab string unchanged.

| `currentTab` | Icon component |
| --- | --- |
| `dashboard` | `Odometer` |
| `validation` | `CircleCheck` |
| `importExport` | `Files` |
| `reports` | `DataAnalysis` |
| `stats` | `TrendCharts` |
| `assets` | `Box` |
| `procurement` | `ShoppingCart` |
| `inbound` | `Download` |
| `outbound` | `Upload` |
| `changes` | `Switch` |
| `faults` | `WarningFilled` |
| `warranties` | `Service` |
| `retirements` | `DeleteFilled` |
| `approval` | `DocumentChecked` |
| `approvalNotify` | `Bell` |
| `users` | `User` |
| `roles` | `Avatar` |
| `config` | `Setting` |

- [ ] **Step 5: Run the contract test to verify GREEN**

Run:

```powershell
python -m pytest tests/test_production_mvp.py::test_frontend_uses_the_modern_operations_console_system -q
```

Expected: pass with the icon CDN, registration loop, and at least 18 `el-icon` menu wrappers.

### Task 5: Browser-level regression and commit

**Files:**

- Modify: `frontend/index.html`
- Modify: `tests/test_production_mvp.py`

- [ ] **Step 1: Start the application locally**

Run:

```powershell
python start.py
```

Expected: the application serves its login page on the configured local port without JavaScript loading errors.

- [ ] **Step 2: Verify the console at 1366px and 900px widths**

In the local browser, sign in with an existing local administrator or a locally seeded test user and inspect dashboard, assets, procurement, inbound, outbound, changes, faults, warranties, retirements, approval, reports, users, roles, and configuration. Do not use a production credential in the local browser.

At 1366px confirm the sidebar, toolbar, table columns, status tags, sub-tabs, dialogs, and drawers are visible without overlap. At 900px confirm the sidebar collapses to icons and filter controls wrap rather than overflow. Perform one non-destructive tab switch and close one dialog; do not submit a form.

- [ ] **Step 3: Run final source verification**

Run:

```powershell
python -m pytest -q
python -m compileall backend -q
git diff --check
```

Expected: tests pass, compilation exits 0, and no whitespace errors are reported.

- [ ] **Step 4: Commit the visual refresh**

```powershell
git add frontend/index.html tests/test_production_mvp.py
git commit -m "feat: refresh operations console UI"
```
