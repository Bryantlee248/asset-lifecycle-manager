from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session

from database import AuditLog


SENSITIVE_FIELDS = {
    "password",
    "password_hash",
    "token",
    "jwt",
    "jwt_secret_key",
}


def sanitize_detail(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: "[REDACTED]"
            if key.lower() in SENSITIVE_FIELDS
            else sanitize_detail(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [sanitize_detail(item) for item in value]
    return value


def record_audit(
    db: Session,
    actor_id: int,
    action: str,
    resource_type: str,
    resource_id: str,
    detail: dict[str, Any],
) -> AuditLog:
    entry = AuditLog(
        user_id=actor_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        detail=json.dumps(sanitize_detail(detail), ensure_ascii=False, default=str),
    )
    db.add(entry)
    return entry
