"""Durable in-app notification creation with uniqueness keys (S3 reminders)."""

from __future__ import annotations

import re
import uuid
from collections.abc import Iterable

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from . import policy
from .models import Notification, User, Workspace

MENTION_RE = re.compile(r"(?<![\w@])@([a-z0-9][a-z0-9._-]{1,62})", re.IGNORECASE)


def create(db: Session, *, recipients: Iterable[uuid.UUID], kind: str, workspace_id, source_type: str,
           source_id: uuid.UUID, occurrence: str) -> int:
    """Insert one notification per recipient and occurrence. Duplicates are ignored."""
    rows = [
        {"id": uuid.uuid4(), "recipient_id": r, "kind": kind, "workspace_id": workspace_id,
         "source_type": source_type, "source_id": source_id,
         "dedupe_key": f"{kind}:{source_type}:{source_id}:{occurrence}:{r}"}
        for r in set(recipients)
    ]
    if not rows:
        return 0
    stmt = (insert(Notification).values(rows).on_conflict_do_nothing(index_elements=["dedupe_key"])
            .returning(Notification.id))
    return len(db.execute(stmt).all())


def mentioned_users(db: Session, body: str, workspace: Workspace, author_id) -> list[uuid.UUID]:
    names = {m.lower() for m in MENTION_RE.findall(body or "")}
    if not names:
        return []
    users = db.scalars(select(User).where(User.username.in_(names), User.is_active.is_(True))).all()
    return [u.id for u in users if u.id != author_id and policy.can_read(db, u, workspace.id)]
