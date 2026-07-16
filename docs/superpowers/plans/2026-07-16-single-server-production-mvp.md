# Single-Server Production MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (\`- [ ]\`) syntax for tracking.

**Goal:** Make the FastAPI and SQLite application safe and observable enough for a single-server deployment with fewer than 10 concurrent writers.

**Architecture:** Add a small runtime-settings module shared by authentication, database, and application startup. Keep business routes unchanged; add a dedicated health router, isolated SQLite tests, and Nginx/systemd templates that leave Nginx as the sole public HTTP entry point.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy, SQLite, pytest, httpx, Uvicorn, Nginx, systemd.

---

## File Structure

- Create: \`backend/settings.py\` - Environment parsing and production validation.
- Create: \`backend/health.py\` - Database health endpoint.
- Create: \`requirements-dev.txt\` - Test-only dependencies.
- Create: \`tests/conftest.py\` - Temporary SQLite environment fixture.
- Create: \`tests/test_production_mvp.py\` - Runtime, bootstrap, SQLite, health, and password-display tests.
- Create: \`tests/test_deployment_templates.py\` - Static checks for deployment safeguards.
- Create: \`deploy/systemd/asset-lifecycle.service\` - Single-worker loopback systemd unit.
- Create: \`deploy/nginx/asset-lifecycle.conf\` - Public HTTP reverse proxy template.
- Create: \`deploy/README.md\` - Operations instructions and HTTPS transition requirement.
- Modify: \`.env.example\`, \`.gitignore\`, \`backend/auth.py\`, \`backend/database.py\`, \`backend/main.py\`, \`start.py\`, \`frontend/index.html\`, and \`README.txt\`.

Do not modify the existing business CRUD, approval, reporting, or legacy mutable functional scripts in this MVP.

### Task 1: Add the isolated test harness

**Files:**
- Create: \`requirements-dev.txt\`
- Create: \`tests/conftest.py\`
- Create: \`tests/test_production_mvp.py\`

- [ ] **Step 1: Write a failing production-settings test**

Create \`tests/test_production_mvp.py\`:

    from pathlib import Path
    import sys
    import pytest

    PROJECT_ROOT = Path(__file__).resolve().parents[1]
    BACKEND_DIR = PROJECT_ROOT / "backend"
    if str(BACKEND_DIR) not in sys.path:
        sys.path.insert(0, str(BACKEND_DIR))

    def test_production_settings_require_a_jwt_secret():
        from settings import ConfigurationError, load_settings

        with pytest.raises(ConfigurationError, match="JWT_SECRET_KEY"):
            load_settings({"ENV": "production"})

- [ ] **Step 2: Install the test dependencies and verify RED**

Create \`requirements-dev.txt\`:

    -r requirements.txt
    pytest>=8.0,<9.0
    httpx>=0.27,<1.0

Run:

    python -m pip install -r requirements-dev.txt
    python -m pytest tests/test_production_mvp.py::test_production_settings_require_a_jwt_secret -q

Expected: FAIL with \`ModuleNotFoundError: No module named 'settings'\`.

- [ ] **Step 3: Add a temporary database fixture**

Create \`tests/conftest.py\`:

    from pathlib import Path
    import sys
    import pytest

    PROJECT_ROOT = Path(__file__).resolve().parents[1]
    BACKEND_DIR = PROJECT_ROOT / "backend"
    if str(BACKEND_DIR) not in sys.path:
        sys.path.insert(0, str(BACKEND_DIR))

    RUNTIME_MODULES = ("settings", "database", "auth", "health", "main")

    @pytest.fixture
    def isolated_runtime(monkeypatch, tmp_path):
        for module_name in RUNTIME_MODULES:
            sys.modules.pop(module_name, None)
        monkeypatch.setenv("ENV", "development")
        monkeypatch.setenv("JWT_SECRET_KEY", "test-jwt-secret")
        monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'test.db'}")
        monkeypatch.delenv("DEFAULT_ADMIN_PASSWORD", raising=False)
        try:
            yield
        finally:
            for module_name in RUNTIME_MODULES:
                sys.modules.pop(module_name, None)

- [ ] **Step 4: Commit the test harness**

    git add requirements-dev.txt tests/conftest.py tests/test_production_mvp.py
    git commit -m "test: add isolated production mvp test harness"

### Task 2: Add runtime settings and production validation

**Files:**
- Create: \`backend/settings.py\`
- Modify: \`backend/auth.py:17-45\`
- Modify: \`backend/main.py:114-129\`
- Test: \`tests/test_production_mvp.py\`

- [ ] **Step 1: Add failing tests for valid production settings and wildcard CORS**

Append:

    def test_production_settings_accept_an_explicit_jwt_secret():
        from settings import load_settings

        settings = load_settings(
            {"ENV": "production", "JWT_SECRET_KEY": "production-secret"}
        )

        assert settings.environment == "production"
        assert settings.jwt_secret_key == "production-secret"
        assert settings.cors_origins == ()

    def test_production_settings_reject_wildcard_cors():
        from settings import ConfigurationError, load_settings

        with pytest.raises(ConfigurationError, match="CORS_ORIGINS"):
            load_settings(
                {
                    "ENV": "production",
                    "JWT_SECRET_KEY": "production-secret",
                    "CORS_ORIGINS": "*",
                }
            )

- [ ] **Step 2: Run the tests and verify RED**

    python -m pytest tests/test_production_mvp.py -q

Expected: FAIL because \`load_settings\` and \`ConfigurationError\` do not exist.

- [ ] **Step 3: Implement the settings module**

Create \`backend/settings.py\`:

    from dataclasses import dataclass
    import os
    from typing import Mapping

    class ConfigurationError(RuntimeError):
        pass

    @dataclass(frozen=True)
    class RuntimeSettings:
        environment: str
        jwt_secret_key: str | None
        cors_origins: tuple[str, ...]
        database_url: str | None
        sqlite_timeout_seconds: int

        @property
        def is_production(self) -> bool:
            return self.environment == "production"

    def load_settings(environ: Mapping[str, str] | None = None) -> RuntimeSettings:
        values = os.environ if environ is None else environ
        environment = values.get("ENV", "development").strip().lower() or "development"
        jwt_secret_key = values.get("JWT_SECRET_KEY", "").strip() or None
        raw_origins = values.get("CORS_ORIGINS", "")
        cors_origins = tuple(
            origin.strip() for origin in raw_origins.split(",") if origin.strip()
        )
        database_url = values.get("DATABASE_URL", "").strip() or None

        if environment == "production" and not jwt_secret_key:
            raise ConfigurationError("Production requires JWT_SECRET_KEY")
        if environment == "production" and "*" in cors_origins:
            raise ConfigurationError("Production CORS_ORIGINS cannot contain '*'")

        if environment != "production" and not cors_origins:
            cors_origins = (
                "http://127.0.0.1:8000",
                "http://localhost:8000",
                "http://127.0.0.1:3000",
                "http://localhost:3000",
                "http://127.0.0.1:5173",
                "http://localhost:5173",
            )

        return RuntimeSettings(
            environment=environment,
            jwt_secret_key=jwt_secret_key,
            cors_origins=cors_origins,
            database_url=database_url,
            sqlite_timeout_seconds=5,
        )

In \`backend/auth.py\`, load settings before any secret-file fallback:

    from settings import load_settings

    settings = load_settings()
    JWT_SECRET_KEY = settings.jwt_secret_key

Retain \`.jwt_dev_key\` only in development. In production, do not read \`.jwt_secret\`; missing \`JWT_SECRET_KEY\` must already have raised \`ConfigurationError\`.

In \`backend/main.py\`, replace the current default-origin block with:

    from settings import load_settings

    settings = load_settings()
    if settings.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=list(settings.cors_origins),
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

- [ ] **Step 4: Verify GREEN**

    python -m pytest tests/test_production_mvp.py -q

Expected: all three settings tests PASS.

- [ ] **Step 5: Commit runtime settings**

    git add backend/settings.py backend/auth.py backend/main.py tests/test_production_mvp.py
    git commit -m "feat: validate production runtime settings"

### Task 3: Require explicit first-production credentials

**Files:**
- Modify: \`backend/auth.py:376-421\`
- Modify: \`start.py:28-55\`
- Modify: \`frontend/index.html:134\`
- Modify: \`.env.example\`
- Modify: \`.gitignore\`
- Test: \`tests/test_production_mvp.py\`

- [ ] **Step 1: Write failing bootstrap and password-display tests**

Append:

    def test_first_production_bootstrap_requires_an_admin_password(
        isolated_runtime, monkeypatch
    ):
        from database import Base, SessionLocal, engine
        from auth import init_default_data

        Base.metadata.create_all(bind=engine)
        monkeypatch.setenv("ENV", "production")
        monkeypatch.delenv("DEFAULT_ADMIN_PASSWORD", raising=False)
        db = SessionLocal()
        try:
            with pytest.raises(RuntimeError, match="DEFAULT_ADMIN_PASSWORD"):
                init_default_data(db)
        finally:
            db.close()

    def test_release_files_do_not_publish_a_default_admin_password():
        forbidden = "Admin@2026!Secure"
        files = [
            PROJECT_ROOT / ".env.example",
            PROJECT_ROOT / "start.py",
            PROJECT_ROOT / "frontend" / "index.html",
            PROJECT_ROOT / "backend" / "auth.py",
        ]
        assert all(forbidden not in path.read_text(encoding="utf-8") for path in files)

- [ ] **Step 2: Run the focused tests and verify RED**

    python -m pytest tests/test_production_mvp.py::test_first_production_bootstrap_requires_an_admin_password tests/test_production_mvp.py::test_release_files_do_not_publish_a_default_admin_password -q

Expected: FAIL because the current code creates the default administrator and contains the published default password.

- [ ] **Step 3: Implement bootstrap validation and remove credential text**

Add this helper to \`backend/auth.py\` and call it immediately before creating a missing \`admin\` user in \`init_default_data\`:

    def get_bootstrap_admin_password(db: Session) -> str | None:
        existing_admin = db.query(User).filter(User.username == "admin").first()
        password = os.environ.get("DEFAULT_ADMIN_PASSWORD", "").strip()
        if existing_admin is None and os.environ.get("ENV", "development").lower() == "production" and not password:
            raise RuntimeError("Production first startup requires DEFAULT_ADMIN_PASSWORD")
        return password or None

Only create a new administrator when the helper returns a password. Keep existing administrator rows unchanged.

Remove \`DEFAULT_ADMIN_PASSWORD\` from \`start.py\` imports and remove the print statement that exposes \`admin / password\`. Delete the credential hint element from \`frontend/index.html\`. Change \`.env.example\` to:

    JWT_SECRET_KEY=
    DEFAULT_ADMIN_PASSWORD=

Ensure \`.gitignore\` contains:

    *.db
    *.log
    .env
    .jwt_secret
    .jwt_dev_key
    .pytest_cache/
    .venv/

- [ ] **Step 4: Verify GREEN and ignored secrets**

    python -m pytest tests/test_production_mvp.py::test_first_production_bootstrap_requires_an_admin_password tests/test_production_mvp.py::test_release_files_do_not_publish_a_default_admin_password -q
    git check-ignore -v asset_lifecycle.db backend/.jwt_secret .env

Expected: both tests PASS and every runtime artifact is ignored.

- [ ] **Step 5: Commit credential hardening**

    git add backend/auth.py start.py frontend/index.html .env.example .gitignore tests/test_production_mvp.py
    git commit -m "fix: require explicit production credentials"

### Task 4: Configure SQLite and add health checks

**Files:**
- Create: \`backend/health.py\`
- Modify: \`backend/database.py:1-33\`
- Modify: \`backend/main.py:17-45,1420-1427\`
- Test: \`tests/test_production_mvp.py\`

- [ ] **Step 1: Write failing SQLite and health tests**

Append:

    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from sqlalchemy import create_engine

    def test_sqlite_engine_enables_required_pragmas(isolated_runtime):
        from database import engine

        with engine.connect() as connection:
            assert connection.exec_driver_sql("PRAGMA foreign_keys").scalar_one() == 1
            assert connection.exec_driver_sql("PRAGMA busy_timeout").scalar_one() >= 5000
            assert connection.exec_driver_sql("PRAGMA journal_mode").scalar_one().lower() == "wal"

    def test_health_router_returns_ok_when_database_is_available(
        isolated_runtime, monkeypatch
    ):
        import health

        health.engine = create_engine("sqlite:///:memory:")
        app = FastAPI()
        app.include_router(health.health_router)

        response = TestClient(app).get("/api/health")

        assert response.status_code == 200
        assert response.json()["status"] == "ok"

    def test_health_router_returns_503_when_database_query_fails(
        isolated_runtime, monkeypatch
    ):
        import health

        health.engine = create_engine("sqlite:///missing-parent-directory/health.db")
        app = FastAPI()
        app.include_router(health.health_router)

        response = TestClient(app).get("/api/health")

        assert response.status_code == 503
        assert response.json() == {"detail": "Database unavailable"}

- [ ] **Step 2: Run the new tests and verify RED**

    python -m pytest tests/test_production_mvp.py::test_sqlite_engine_enables_required_pragmas tests/test_production_mvp.py::test_health_router_returns_ok_when_database_is_available tests/test_production_mvp.py::test_health_router_returns_503_when_database_query_fails -q

Expected: FAIL because WAL and busy timeout are absent and \`health.py\` does not exist.

- [ ] **Step 3: Implement the database settings and health router**

At the top of \`backend/database.py\`, use settings and preserve the existing local SQLite path as fallback:

    from settings import load_settings

    settings = load_settings()
    _DB_DIR = os.path.dirname(os.path.abspath(__file__))
    DATABASE_URL = settings.database_url or f"sqlite:///{os.path.join(_DB_DIR, '..', 'asset_lifecycle.db')}"
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False, "timeout": settings.sqlite_timeout_seconds},
    )

Extend the existing connection listener:

    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA busy_timeout=5000")

Create \`backend/health.py\`:

    from fastapi import APIRouter, HTTPException
    from sqlalchemy import text
    from sqlalchemy.exc import SQLAlchemyError

    from database import engine

    health_router = APIRouter()

    @health_router.get("/api/health")
    def health_check():
        try:
            with engine.connect() as connection:
                connection.execute(text("SELECT 1"))
        except SQLAlchemyError:
            raise HTTPException(status_code=503, detail="Database unavailable")
        return {"status": "ok", "version": "3.0.0"}

Import \`health_router\` in \`backend/main.py\` and call \`app.include_router(health_router)\` once after creating \`app\`.

- [ ] **Step 4: Verify GREEN**

    python -m pytest tests/test_production_mvp.py::test_sqlite_engine_enables_required_pragmas tests/test_production_mvp.py::test_health_router_returns_ok_when_database_is_available tests/test_production_mvp.py::test_health_router_returns_503_when_database_query_fails -q

Expected: all three tests PASS using the temporary SQLite database.

- [ ] **Step 5: Commit SQLite and health support**

    git add backend/database.py backend/health.py backend/main.py tests/test_production_mvp.py
    git commit -m "feat: add sqlite health checks and connection safeguards"

### Task 5: Add Nginx and systemd deployment templates

**Files:**
- Create: \`deploy/systemd/asset-lifecycle.service\`
- Create: \`deploy/nginx/asset-lifecycle.conf\`
- Create: \`deploy/README.md\`
- Create: \`tests/test_deployment_templates.py\`
- Modify: \`README.txt\`

- [ ] **Step 1: Write failing template tests**

Create \`tests/test_deployment_templates.py\`:

    from pathlib import Path

    PROJECT_ROOT = Path(__file__).resolve().parents[1]

    def test_systemd_template_uses_a_single_loopback_worker():
        content = (PROJECT_ROOT / "deploy/systemd/asset-lifecycle.service").read_text(encoding="utf-8")
        assert "User=asset-lifecycle" in content
        assert "EnvironmentFile=/etc/asset-lifecycle/asset-lifecycle.env" in content
        assert "--host 127.0.0.1" in content
        assert "--port 8000" in content
        assert "--workers 1" in content

    def test_nginx_template_is_the_public_http_entry_point():
        content = (PROJECT_ROOT / "deploy/nginx/asset-lifecycle.conf").read_text(encoding="utf-8")
        assert "listen 80;" in content
        assert "proxy_pass http://127.0.0.1:8000;" in content
        assert "client_max_body_size 10m;" in content

    def test_deployment_readme_requires_https_before_formal_public_use():
        content = (PROJECT_ROOT / "deploy/README.md").read_text(encoding="utf-8")
        assert "HTTPS" in content
        assert "HTTP" in content
        assert "127.0.0.1:8000" in content

- [ ] **Step 2: Run the tests and verify RED**

    python -m pytest tests/test_deployment_templates.py -q

Expected: FAIL with \`FileNotFoundError\` because \`deploy/\` is absent.

- [ ] **Step 3: Create deployment assets**

Create \`deploy/systemd/asset-lifecycle.service\`:

    [Unit]
    Description=IT Asset Lifecycle Manager
    After=network.target

    [Service]
    Type=simple
    User=asset-lifecycle
    Group=asset-lifecycle
    WorkingDirectory=/opt/asset-lifecycle-manager
    EnvironmentFile=/etc/asset-lifecycle/asset-lifecycle.env
    ExecStart=/opt/asset-lifecycle-manager/.venv/bin/python -m uvicorn main:app --app-dir /opt/asset-lifecycle-manager/backend --host 127.0.0.1 --port 8000 --workers 1
    Restart=on-failure
    RestartSec=5
    NoNewPrivileges=true
    PrivateTmp=true

    [Install]
    WantedBy=multi-user.target

Create \`deploy/nginx/asset-lifecycle.conf\`:

    server {
        listen 80;
        server_name _;
        client_max_body_size 10m;

        location / {
            proxy_pass http://127.0.0.1:8000;
            proxy_http_version 1.1;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }
    }

Create \`deploy/README.md\` with instructions for: environment-file permission \`chmod 600\`; database backup using \`sqlite3 .backup\`; \`PRAGMA integrity_check\`; systemd reload and restart; Nginx syntax test and reload; firewall policy opening only SSH and HTTP; and the rule that public HTTP is temporary and HTTPS is required before formal public use.

Update \`README.txt\` to use \`python -m pip install -r requirements-dev.txt\` for test setup and link to \`deploy/README.md\` for deployment preparation.

- [ ] **Step 4: Verify GREEN**

    python -m pytest tests/test_deployment_templates.py -q

Expected: all three tests PASS.

- [ ] **Step 5: Commit deployment assets**

    git add deploy tests/test_deployment_templates.py README.txt
    git commit -m "docs: add single-server deployment templates"

### Task 6: Run the MVP release gate

**Files:**
- Modify only files named above if a release-gate failure identifies an MVP defect.
- Test: \`tests/test_production_mvp.py\`, \`tests/test_deployment_templates.py\`

- [ ] **Step 1: Run the isolated MVP tests**

    python -m pytest tests/test_production_mvp.py tests/test_deployment_templates.py -q

Expected: all new MVP tests PASS. Do not run historical mutable functional scripts in this gate.

- [ ] **Step 2: Parse all Python source without importing application modules**

    python -c "import ast,pathlib; files=list(pathlib.Path('backend').glob('*.py'))+[pathlib.Path('start.py')]; [ast.parse(path.read_text(encoding='utf-8')) for path in files]; print(f'Parsed {len(files)} Python files')"

Expected: the command prints the current backend-plus-start file count with no syntax error.

- [ ] **Step 3: Confirm runtime secrets are ignored and runtime source has no default password**

    git check-ignore -v asset_lifecycle.db backend/.jwt_secret .env
    rg -n "Admin@2026!Secure|admin123" backend start.py frontend .env.example

Expected: ignore rules are reported and \`rg\` returns no runtime-source, frontend, or environment-example matches. Historic QA artifacts and legacy tests are excluded from this check.

- [ ] **Step 4: Inspect the final repository state**

    git diff --check
    git status --short
    git log --oneline -5

Expected: no whitespace errors and a clean worktree after committing any verification-only correction.

- [ ] **Step 5: Record delivery constraints**

The final delivery note must state that the application remains HTTP-only for temporary public-IP verification and that a domain plus HTTPS are required before formal public use.
