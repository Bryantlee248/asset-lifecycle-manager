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
