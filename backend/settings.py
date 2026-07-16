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
    cors_origins = tuple(origin.strip() for origin in raw_origins.split(",") if origin.strip())
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
