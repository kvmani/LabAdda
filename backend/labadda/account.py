"""Self-service account reads: own record, access and active sessions (PO-25)."""

import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import people_profile
from .config import Settings
from .models import AuthSession
from .security import session_valid, utcnow

ACCESS_LIMIT = 200
SESSION_LIMIT = 50


def own_profile(db: Session, user_id: uuid.UUID) -> dict:
    """Staff record and retained grants; the person can read but not edit either."""
    return {
        "record": people_profile.profile(db, user_id),
        "access": people_profile.access_page(db, user_id, ACCESS_LIMIT, None)["memberships"],
    }


def _iso(value: datetime) -> str:
    return value.isoformat()


def own_sessions(db: Session, user_id: uuid.UUID, current_id: str, settings: Settings) -> list[dict]:
    """Live desk sessions with a public id; the cookie-derived id and tokens are never returned."""
    now = utcnow()
    rows = db.scalars(
        select(AuthSession)
        .where(
            AuthSession.user_id == user_id,
            AuthSession.kind == "normal",
            AuthSession.revoked_at.is_(None),
            AuthSession.expires_at > now,
        )
        .order_by(AuthSession.last_seen_at.desc())
        .limit(SESSION_LIMIT)
    ).all()
    items = [
        {
            "id": str(row.public_id),
            "browser": row.agent_label or "Unknown browser",
            "started_at": _iso(row.created_at),
            "last_seen_at": _iso(row.last_seen_at),
            "current": row.id == current_id,
        }
        for row in rows
        if session_valid(row, settings, now)
    ]
    return sorted(items, key=lambda item: not item["current"])
