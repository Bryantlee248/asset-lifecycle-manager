from pathlib import Path
import asyncio
import os
import subprocess
import sys

import httpx
from fastapi import FastAPI
import pytest
from sqlalchemy import create_engine


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = PROJECT_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


def test_production_settings_require_a_jwt_secret():
    from settings import ConfigurationError, load_settings

    with pytest.raises(ConfigurationError, match="JWT_SECRET_KEY"):
        load_settings({"ENV": "production"})


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


def test_auth_requires_environment_jwt_even_when_secret_file_exists(tmp_path):
    secret_path = BACKEND_DIR / ".jwt_secret"
    previous_content = secret_path.read_bytes() if secret_path.exists() else None
    secret_path.write_text("legacy-file-secret", encoding="utf-8")

    environment = os.environ.copy()
    environment["ENV"] = "production"
    environment["DATABASE_URL"] = f"sqlite:///{tmp_path / 'auth-test.db'}"
    environment.pop("JWT_SECRET_KEY", None)

    try:
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                "import sys; sys.path.insert(0, r'" + str(BACKEND_DIR) + "'); import auth",
            ],
            cwd=PROJECT_ROOT,
            env=environment,
            capture_output=True,
            text=True,
            check=False,
        )
    finally:
        if previous_content is None:
            secret_path.unlink()
        else:
            secret_path.write_bytes(previous_content)

    assert result.returncode != 0
    assert "JWT_SECRET_KEY" in result.stderr


def test_first_production_bootstrap_requires_an_admin_password(
    isolated_runtime, monkeypatch
):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from database import Base
    from auth import init_default_data

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine)
    monkeypatch.setenv("ENV", "production")
    monkeypatch.delenv("DEFAULT_ADMIN_PASSWORD", raising=False)
    db = session_factory()
    try:
        with pytest.raises(RuntimeError, match="DEFAULT_ADMIN_PASSWORD"):
            init_default_data(db)
    finally:
        db.close()


def test_release_files_do_not_publish_a_default_admin_password():
    forbidden_values = ("Admin@2026!Secure", "admin123")
    files = [
        PROJECT_ROOT / ".env.example",
        PROJECT_ROOT / "start.py",
        PROJECT_ROOT / "frontend" / "index.html",
        PROJECT_ROOT / "backend" / "auth.py",
    ]

    assert all(
        forbidden not in path.read_text(encoding="utf-8")
        for forbidden in forbidden_values
        for path in files
    )


def test_database_uses_the_configured_url(isolated_runtime):
    from database import DATABASE_URL

    assert DATABASE_URL.endswith("test.db")


def test_sqlite_engine_enables_required_pragmas(isolated_runtime):
    from database import engine

    with engine.connect() as connection:
        assert connection.exec_driver_sql("PRAGMA foreign_keys").scalar_one() == 1
        assert connection.exec_driver_sql("PRAGMA busy_timeout").scalar_one() >= 5000
        assert connection.exec_driver_sql("PRAGMA journal_mode").scalar_one().lower() == "wal"


def get_response(app: FastAPI, path: str) -> httpx.Response:
    async def request() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            return await client.get(path)

    return asyncio.run(request())


def test_health_router_returns_ok_when_database_is_available(isolated_runtime):
    import health

    health.engine = create_engine("sqlite:///:memory:")
    app = FastAPI()
    app.include_router(health.health_router)

    response = get_response(app, "/api/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_health_router_returns_503_when_database_query_fails(isolated_runtime):
    import health

    health.engine = create_engine("sqlite:///missing-parent-directory/health.db")
    app = FastAPI()
    app.include_router(health.health_router)

    response = get_response(app, "/api/health")

    assert response.status_code == 503
    assert response.json() == {"detail": "Database unavailable"}


def test_default_pytest_collection_only_includes_release_gates():
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "tests/test_production_mvp.py" in result.stdout
    assert "tests/test_deployment_templates.py" in result.stdout
    assert "tests/test_approval.py" not in result.stdout
    assert "tests/functional_test.py" not in result.stdout
