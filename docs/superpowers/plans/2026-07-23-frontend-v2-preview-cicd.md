# Frontend V2 Preview CI/CD Integration Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Publish the already-built `frontend-v2` UI through the existing GitHub Actions CI/CD pipeline at `/preview/`, while keeping the current `/` production UI unchanged for rollback.

**Architecture:** CI installs Node, verifies `frontend-v2`, builds it with `VITE_BASE=/preview/`, and packages the generated `frontend-v2/dist`. FastAPI mounts that dist directory at `/preview` with static HTML support. The old `frontend/` entry remains the root page.

**Tech Stack:** FastAPI `StaticFiles`, GitHub Actions, Node 20, Vite/Vue, pytest.

---

### Task 1: Lock the CI/CD and backend preview contract with failing tests

**Files:**
- Modify: `tests/test_deployment_templates.py`

- [ ] **Step 1: Add tests asserting CI builds V2 and backend serves `/preview`.**

```python
def test_ci_builds_frontend_v2_preview_before_packaging():
    workflow = (PROJECT_ROOT / ".github/workflows/ci-cd.yml").read_text(encoding="utf-8")

    assert "actions/setup-node@v4" in workflow
    assert "node-version: \"20\"" in workflow
    assert "working-directory: frontend-v2" in workflow
    assert "npm ci" in workflow
    assert "npm run typecheck" in workflow
    assert "npm run test:unit" in workflow
    assert "npm run build:preview" in workflow
    assert workflow.index("npm run build:preview") < workflow.index("Package release")


def test_backend_serves_frontend_v2_dist_under_preview_only():
    content = (PROJECT_ROOT / "backend/main.py").read_text(encoding="utf-8")

    assert 'frontend_dir = os.path.join(os.path.dirname(__file__), "..", "frontend")' in content
    assert 'frontend_v2_dist_dir = os.path.join(os.path.dirname(__file__), "..", "frontend-v2", "dist")' in content
    assert 'app.mount("/preview", StaticFiles(directory=frontend_v2_dist_dir, html=True), name="frontend-v2-preview")' in content
    assert 'app.mount("/static", StaticFiles(directory=frontend_dir), name="static")' in content
```

- [ ] **Step 2: Run the focused tests and verify they fail for missing V2 integration.**

Run: `python -m pytest tests/test_deployment_templates.py -q`

Expected: fails on the two new tests because CI and backend do not yet reference `frontend-v2`.

### Task 2: Implement the minimal integration

**Files:**
- Modify: `backend/main.py`
- Modify: `.github/workflows/ci-cd.yml`

- [ ] **Step 1: Add the `/preview` static mount.**

Add `frontend_v2_dist_dir` next to the existing `frontend_dir`, and mount it only when the dist directory exists:

```python
frontend_v2_dist_dir = os.path.join(os.path.dirname(__file__), "..", "frontend-v2", "dist")
if os.path.exists(frontend_v2_dist_dir):
    app.mount("/preview", StaticFiles(directory=frontend_v2_dist_dir, html=True), name="frontend-v2-preview")
```

- [ ] **Step 2: Add frontend-v2 CI verification before Python CI and before packaging.**

Add Node setup and a `frontend-v2` verification step that runs:

```bash
npm ci
npm run typecheck
npm run test:unit
npm run build:preview
```

### Task 3: Verify, commit, push, and observe deployment

**Files:**
- Track: `frontend-v2/`
- Track: modified CI/backend/tests/plan files.

- [ ] **Step 1: Run local gates.**

Run:

```bash
python -m pytest tests/test_deployment_templates.py -q
python -m pytest -q --disable-warnings
python -m compileall backend -q
cd frontend-v2 && npm run typecheck && npm run test:unit && npm run build:preview && npm audit --omit=dev
git diff --check
```

- [ ] **Step 2: Commit only source and config files.**

Do not commit `node_modules`, `dist`, `dist-preview`, `test-results`, or timestamp cache files.

- [ ] **Step 3: Push to `main` and monitor GitHub Actions.**

Expected: GitHub Actions completes CI and deploy jobs.

- [ ] **Step 4: Verify remote endpoints.**

Run:

```bash
curl -fsS http://125.77.25.229:8081/api/health
curl -fsS http://125.77.25.229:8081/preview/
```

Expected: health returns JSON `status=ok`; `/preview/` returns the Vite HTML entry.
