# Full System UI Modernization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Modernize every existing frontend page into a coherent IT asset operations console without changing APIs, permissions, lifecycle behavior, approval behavior, or existing `currentTab` values.

**Architecture:** Keep the single-file Vue 3 SPA and its current state/data-loading functions. Add a small set of reusable CSS layout primitives and reorganize only the navigation markup and existing page markup around the approved five-domain information architecture. Protect the public shell and responsive behavior with static contract tests, then exercise the actual flows in a local isolated browser session.

**Tech Stack:** Vue 3.5.13 global build, Element Plus 2.9.1, Element Plus icons 2.3.1, ECharts 5.5.0, pytest.

---

### Task 1: Protect the baseline and add UI contract coverage

**Files:**

- Modify: `tests/test_production_mvp.py`
- Read: `AGENTS.md`, `docs/handoff/ui-modernization/PRD.md`, `docs/handoff/ui-modernization/PAGE-MAPPING.md`, `docs/handoff/ui-modernization/TECHNICAL-SPEC.md`

- [ ] **Step 1: Record the existing baseline without changing files**

Run:

```powershell
git status --short
git log -1 --oneline
python -m pytest -q --disable-warnings
```

Expected: the worktree may already be dirty; do not remove or stage unrelated files, and the existing suite passes before UI work starts.

- [ ] **Step 2: Add a failing static contract for the new shell**

Add a focused test that reads `frontend/index.html` and asserts the five visible domain labels, the existing tab identifiers, and a narrow-screen navigation selector. The assertion must name real required strings, for example:

```python
def test_frontend_groups_existing_tabs_into_the_five_operations_domains():
    html = (PROJECT_ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    required_labels = ("工作台", "资产运营", "协同中心", "洞察报告", "系统治理")
    required_tabs = ("'dashboard'", "'assets'", "'approval'", "'reports'", "'config'")
    assert all(label in html for label in required_labels)
    assert all(tab in html for tab in required_tabs)
```

- [ ] **Step 3: Run the focused test and verify failure**

Run:

```powershell
python -m pytest tests/test_production_mvp.py -q --disable-warnings
```

Expected: failure only if the current shell does not yet meet the new navigation contract.

- [ ] **Step 4: Do not weaken existing UI contract tests**

Keep the token, selector, icon-loading, no-gradient and icon-count assertions in `test_frontend_uses_the_modern_operations_console_system`. Update them only when an equivalent or stronger implementation contract replaces a selector.

### Task 2: Implement the global app shell and five-domain navigation

**Files:**

- Modify: `frontend/index.html` CSS near the existing `:root`, `.app-header`, `.sidebar`, `.main-content`, and media queries
- Modify: `frontend/index.html` navigation markup near `<!-- 左侧菜单 -->`
- Test: `tests/test_production_mvp.py`

- [ ] **Step 1: Add only shared visual primitives**

Define or refine CSS for a page header, page heading/action row, dense list toolbar, status label, responsive navigation trigger, and an accessible narrow-screen drawer. Reuse the current color tokens and Element Plus variables; do not add a new CSS framework or `linear-gradient`.

- [ ] **Step 2: Regroup menu items while preserving click expressions**

Use the five labels exactly: `工作台` (`dashboard`, `validation`), `资产运营` (`assets`, `procurement`, `inbound`, `outbound`, `changes`, `faults`, `warranties`, `retirements`), `协同中心` (`approval`, `approvalNotify`, `importExport`), `洞察报告` (`reports`, `stats`), `系统治理` (`users`, `roles`, `config`). Keep each existing `v-if`, `@click`, method invocation and `currentTab` literal unchanged.

- [ ] **Step 3: Implement a narrow-screen navigation path**

At widths at or below 900px, make navigation labels available through a visible menu/drawer interaction. The desktop sidebar may collapse, but users must still be able to discover and select every authorized menu item by text.

- [ ] **Step 4: Run focused contracts**

Run:

```powershell
python -m pytest tests/test_production_mvp.py -q --disable-warnings
```

Expected: the existing operations-console contract and the new five-domain contract pass.

### Task 3: Apply the approved list and detail patterns to asset operations

**Files:**

- Modify: `frontend/index.html` templates for `assets`, `procurement`, `inbound`, `outbound`, `changes`, `faults`, `warranties`, and `retirements`
- Modify: `frontend/index.html` existing dialog and form styles only when required by the pattern
- Test: `tests/test_production_mvp.py`

- [ ] **Step 1: Normalize list page structure**

For each listed tab, retain all existing filters, buttons, columns, form bindings and handlers. Wrap the existing content in the same order: page heading with one primary action, filter/toolbar, table/content, pagination or empty state. Do not change field names or API methods.

- [ ] **Step 2: Normalize detail and operation views**

Where an existing detail dialog exists, present object code/name, current stage/status, location, responsible person, next action, associated records and audit/timeline information before secondary fields. Keep existing confirmations for approval, removal and destructive actions.

- [ ] **Step 3: Preserve lifecycle visual semantics**

Keep all seven stages: `规划`、`在途`、`上架`、`运行`、`维修`、`待报废`、`已报废`. Each status must have visible text in addition to its color and must not alter validation/transition methods.

- [ ] **Step 4: Run approval and full regression**

Run:

```powershell
python -m pytest tests/test_approval.py -q --disable-warnings
python -m pytest -q --disable-warnings
```

Expected: approval fixtures and the full release gate pass.

### Task 4: Modernize workbench, collaboration, reports and governance pages

**Files:**

- Modify: `frontend/index.html` templates for `dashboard`, `validation`, `approval`, `approvalNotify`, `importExport`, `reports`, `stats`, `users`, `roles`, and `config`
- Test: `tests/test_production_mvp.py`

- [ ] **Step 1: Prioritize actionable work on the dashboard**

Use existing loaded data to place pending approvals, active faults, expiring warranties, risk/validation counts and primary shortcuts before lower-priority statistics. Do not invent server-side metrics or display fabricated values when an API returns no data.

- [ ] **Step 2: Preserve approval and configuration tab state**

Retain `approvalSubTab`, `configSubTab`, `configDomain`, `onApprovalSubTabChange`, `onConfigSubTabChange`, `onConfigDomainChange`, `loadConfig`, `loadApprovalNotifications`, all filter variables and their current loading calls. Modernize only presentation and hierarchy.

- [ ] **Step 3: Apply the management pattern**

Give users, roles and configuration pages clear page titles, scoped actions, explanations of configuration impact, permission-aware controls and existing restore-default entry points. Keep `config:manage`, `users:view`, `roles:view`, `approval:view` and `reports:view` checks intact.

- [ ] **Step 4: Run the full suite**

Run:

```powershell
python -m pytest -q --disable-warnings
```

Expected: all tests pass without skipping or deleting assertions.

### Task 5: Responsive verification and delivery evidence

**Files:**

- Modify only if defects are found: `frontend/index.html`, `tests/test_production_mvp.py`
- Do not modify: `backend/`, deployment, QA scripts, CI, production configuration

- [ ] **Step 1: Verify isolated local browser flows**

Use an isolated local database and a local server. Verify login, all authorized first-level domains, asset list/filter/create/edit, a stage transition, approval detail/action, configuration navigation and report/chart loading at 1440px, 768px and 375px.

- [ ] **Step 2: Fix only observed defects**

Correct overlap, inaccessible controls, hidden navigation labels, table overflow, modal clipping, missing loading/empty/error states, or changed handlers. Do not refactor unrelated backend or data code.

- [ ] **Step 3: Run final verification**

Run:

```powershell
python -m pytest -q --disable-warnings
python -m compileall backend -q
git diff --check
```

Expected: tests pass, backend compilation succeeds, and the diff has no whitespace errors.

- [ ] **Step 4: Prepare handoff without Git or deployment actions**

Report modified files, retained contracts, test output, browser evidence, known limitations, and explicitly state that no commit, push, deployment, remote access or destructive QA script was performed unless separately authorized.
