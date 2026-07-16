from pathlib import Path
import os
import subprocess
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
