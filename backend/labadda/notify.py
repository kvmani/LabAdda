"""Durable in-app notification creation with uniqueness keys (S3 reminders)."""

from __future__ import annotations

import re
import uuid
from collections.abc import Iterable

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from . import metrics, policy
from .models import Notification, NotificationPreference, User, Workspace

MENTION_RE = re.compile(r"(?<![\w@])@([a-z0-9][a-z0-9._-]{1,62})", re.IGNORECASE)


def create(
    db: Session,
    *,
    recipients: Iterable[uuid.UUID],
    kind: str,
    workspace_id,
    source_type: str,
    source_id: uuid.UUID,
    occurrence: str,
) -> int:
    """Insert one notification per recipient and occurrence. Duplicates are ignored."""
    candidates = {uuid.UUID(str(recipient)) for recipient in recipients}
    field = {"mention": "mentions", "official": "official_notices", "reminder": "reminders"}.get(kind)
    preferences = (
        {
            row.user_id: row
            for row in db.scalars(
                select(NotificationPreference).where(NotificationPreference.user_id.in_(candidates))
            )
        }
        if field and candidates
        else {}
    )
    # Choices apply when an occurrence is queued. Already queued alerts/history
    # are retained; enabling a category never replays skipped occurrences.
    allowed = {
        recipient
        for recipient in candidates
        if recipient not in preferences or getattr(preferences[recipient], field)
    }
    rows = [
        {
            "id": uuid.uuid4(),
            "recipient_id": r,
            "kind": kind,
            "workspace_id": workspace_id,
            "source_type": source_type,
            "source_id": source_id,
            "dedupe_key": f"{kind}:{source_type}:{source_id}:{occurrence}:{r}",
        }
        for r in allowed
    ]
    if not rows:
        return 0
    stmt = (
        insert(Notification)
        .values(rows)
        .on_conflict_do_nothing(index_elements=["dedupe_key"])
        .returning(Notification.id)
    )
    created = len(db.execute(stmt).all())
    # Personal-note reminders have no workspace and stay outside analytics.
    if created and workspace_id is not None:
        workspace = db.get(Workspace, uuid.UUID(str(workspace_id)))
        metrics.count_workspace_on_commit(db, "notifications.created", workspace, created)
    return created


def mentioned_users(db: Session, body: str, workspace: Workspace, author_id) -> list[uuid.UUID]:
    names = {m.lower() for m in MENTION_RE.findall(body or "")}
    if not names:
        return []
    users = db.scalars(select(User).where(User.username.in_(names), User.is_active.is_(True))).all()
    return [u.id for u in users if u.id != author_id and policy.can_read(db, u, workspace.id)]
