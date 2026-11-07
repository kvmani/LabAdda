"""Restricted audit trail for identity, membership and hierarchy changes."""

from __future__ import annotations

from sqlalchemy.orm import Session

from .models import AuditEvent


def record(
    db: Session,
    *,
    actor,
    action: str,
    scope_type: str,
    scope_id=None,
    target_id=None,
    outcome: str = "success",
    reason: str | None = None,
    **detail,
) -> None:
    db.add(
        AuditEvent(
            actor_id=getattr(actor, "id", actor),
            action=action,
            scope_type=scope_type,
            scope_id=str(scope_id) if scope_id else None,
            target_id=str(target_id) if target_id else None,
            outcome=outcome,
            reason=reason,
            detail={k: (str(v) if v is not None else None) for k, v in detail.items()},
        )
    )
