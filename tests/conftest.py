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
