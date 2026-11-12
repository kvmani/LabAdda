"""In-app notifications. Eligibility is rechecked whenever they are listed or opened."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from .. import policy
from ..changes.kinds import transfer
from ..deps import Actor, current_actor, get_db
from ..errors import NotFound
from ..models import ChatMessage, Note, Notification, Post, User, Workspace
from ..security import utcnow
from ..serialize import iso

router = APIRouter(prefix="/notifications", tags=["notifications"])


def _resolve(db: Session, actor: Actor, n: Notification, readable: dict) -> dict | None:
    """Return display data if the recipient may still see the source, else None."""
    if n.source_type == "note":
        note = db.get(Note, n.source_id)
        if note is None or note.owner_id != actor.id:
            return None
        return {
            "title": note.title or note.body[:80],
            "workspace": None,
            "link": {"view": "notes", "id": str(note.id)},
        }
    if n.source_type == "post":
        post = db.get(Post, n.source_id)
        if post is None or post.deleted_at is not None or post.workspace_id not in readable:
            return None
        ws = db.get(Workspace, post.workspace_id)
        return {
            "title": post.body[:120],
            "workspace": {"id": str(ws.id), "name": ws.name},
            "link": {
                "view": "noticeboard",
                "workspace_id": str(ws.id),
                "post_id": str(post.parent_id or post.id),
            },
        }
    if n.source_type == "chat":
        msg = db.get(ChatMessage, n.source_id)
        if msg is None or msg.workspace_id not in readable:
            return None
        ws = db.get(Workspace, msg.workspace_id)
        return {
            "title": msg.body[:120],
            "workspace": {"id": str(ws.id), "name": ws.name},
            "link": {"view": "chat", "workspace_id": str(ws.id), "seq": msg.seq},
        }
    if n.source_type == "transfer":
        return _reassignment(db, n, readable)
    return None


def _reassignment(db: Session, n: Notification, readable: dict) -> dict | None:
    """Steward notice after a transfer: the person's name and a live count, never task text."""
    person = db.get(User, n.source_id)
    if person is None or n.workspace_id not in readable:
        return None
    ws = db.get(Workspace, n.workspace_id)
    count = transfer.open_task_counts(db, person.id, {ws.id}).get(ws.id, 0)
    return {
        "title": (
            f"{person.display_name} has moved to another unit. {count} open shared tasks in this "
            "workspace are still assigned to them. Please reassign them."
        ),
        "workspace": {"id": str(ws.id), "name": ws.name},
        "link": {"view": "todos", "workspace_id": str(ws.id)},
    }


def _visible(db: Session, actor: Actor, limit: int, unread_only: bool = False):
    readable = policy.readable_workspace_ids(db, actor.user)
    stmt = select(Notification).where(Notification.recipient_id == actor.id)
    if unread_only:
        stmt = stmt.where(Notification.read_at.is_(None))
    out = []
    for n in db.scalars(stmt.order_by(Notification.created_at.desc()).limit(limit * 3)):
        info = _resolve(db, actor, n, readable)
        if info is not None:
            out.append((n, info))
        if len(out) >= limit:
            break
    return out


@router.get("")
def list_notifications(
    limit: int = Query(default=30, le=100),
    actor: Actor = Depends(current_actor),
    db: Session = Depends(get_db),
):
    items = _visible(db, actor, limit)
    unread = len(_visible(db, actor, 100, unread_only=True))
    return {
        "unread": unread,
        "items": [
            {
                "id": str(n.id),
                "kind": n.kind,
                "created_at": iso(n.created_at),
                "read": n.read_at is not None,
                **info,
            }
            for n, info in items
        ],
    }


@router.post("/{notification_id}/open")
def open_notification(
    notification_id: uuid.UUID, actor: Actor = Depends(current_actor), db: Session = Depends(get_db)
):
    n = db.get(Notification, notification_id)
    if n is None or n.recipient_id != actor.id:
        raise NotFound()
    info = _resolve(db, actor, n, policy.readable_workspace_ids(db, actor.user))
    if info is None:
        raise NotFound()
    n.read_at = n.read_at or utcnow()
    db.commit()
    return {"id": str(n.id), "kind": n.kind, **info}


@router.post("/read-all")
def read_all(actor: Actor = Depends(current_actor), db: Session = Depends(get_db)):
    db.execute(
        update(Notification)
        .where(Notification.recipient_id == actor.id, Notification.read_at.is_(None))
        .values(read_at=utcnow())
    )
    db.commit()
    return {"ok": True}
