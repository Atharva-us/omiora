"""Hash-chained, append-only audit log.

Each row stores `hash = sha256(prev_hash + canonical_json(fields))`. Appends take a
transaction-scoped advisory lock so the chain is linear. A database trigger rejects UPDATE and
DELETE (migration 0001); `verify_audit_chain` detects rows altered at the storage level.
Never put secrets or full user content in `data`; store identifiers and summaries.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any, Literal

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from .db.models import AuditLog

GENESIS = "0" * 64
_AUDIT_LOCK_KEY = 0x0A0D17  # arbitrary constant identifying the audit chain lock

ActorType = Literal["user", "worker", "system"]


def _digest(prev_hash: str, fields: dict[str, Any]) -> str:
    canonical = json.dumps(fields, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256((prev_hash + canonical).encode()).hexdigest()


def _fields(row: AuditLog) -> dict[str, Any]:
    return {
        "at": row.at.astimezone(UTC).isoformat(),
        "actor_type": row.actor_type,
        "actor_id": row.actor_id,
        "action": row.action,
        "entity_type": row.entity_type,
        "entity_id": row.entity_id,
        "data": row.data,
    }


def append_audit(
    session: Session,
    *,
    actor_type: ActorType,
    actor_id: str | None,
    action: str,
    entity_type: str,
    entity_id: str,
    data: dict[str, Any] | None = None,
    at: datetime | None = None,
) -> AuditLog:
    session.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": _AUDIT_LOCK_KEY})
    prev_hash = session.scalar(select(AuditLog.hash).order_by(AuditLog.id.desc()).limit(1)) or GENESIS
    row = AuditLog(
        at=(at or datetime.now(UTC)).replace(microsecond=0),
        actor_type=actor_type,
        actor_id=actor_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        data=data or {},
        prev_hash=prev_hash,
        hash="",
    )
    row.hash = _digest(prev_hash, _fields(row))
    session.add(row)
    session.flush()
    return row


def verify_audit_chain(session: Session) -> int | None:
    """Returns the id of the first row that breaks the chain, or None if the chain is intact."""
    prev_hash = GENESIS
    for row in session.scalars(select(AuditLog).order_by(AuditLog.id)):
        if row.prev_hash != prev_hash or row.hash != _digest(prev_hash, _fields(row)):
            return row.id
        prev_hash = row.hash
    return None
