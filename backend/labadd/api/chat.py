"""Workspace chat stream with idempotent sends and cursor replay (S3)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from .. import notify, policy
from ..deps import Actor, current_actor, get_db
from ..errors import Conflict
from ..models import ChatMessage, ChatRead
from ..serialize import iso, user_brief, users_by_id

router = APIRouter(tags=["chat"])


class NewMessage(BaseModel):
    body: str = Field(min_length=1, max_length=4000)
    client_id: str = Field(min_length=8, max_length=64)


class ReadBody(BaseModel):
    seq: int


def message_json(m: ChatMessage, authors: dict) -> dict:
    return {"id": str(m.id), "seq": m.seq, "workspace_id": str(m.workspace_id), "body": m.body,
            "client_id": m.client_id, "created_at": iso(m.created_at), "author": user_brief(authors.get(m.author_id))}


@router.get("/workspaces/{workspace_id}/chat")
def history(workspace_id: uuid.UUID, before: int | None = None, after: int | None = None,
            limit: int = Query(default=50, ge=1, le=200), actor: Actor = Depends(current_actor),
            db: Session = Depends(get_db)):
    policy.require_read(db, actor.user, workspace_id)
    stmt = select(ChatMessage).where(ChatMessage.workspace_id == workspace_id)
    if after is not None:
        rows = db.scalars(stmt.where(ChatMessage.seq > after).order_by(ChatMessage.seq).limit(limit + 1)).all()
        more = len(rows) > limit
        rows = rows[:limit]
    else:
        if before is not None:
            stmt = stmt.where(ChatMessage.seq < before)
        rows = db.scalars(stmt.order_by(ChatMessage.seq.desc()).limit(limit + 1)).all()
        more = len(rows) > limit
        rows = list(reversed(rows[:limit]))
    authors = users_by_id(db, [m.author_id for m in rows])
    last_read = db.scalar(select(ChatRead.last_seq).where(ChatRead.user_id == actor.id,
                                                          ChatRead.workspace_id == workspace_id)) or 0
    return {"messages": [message_json(m, authors) for m in rows], "has_more": more, "last_read_seq": last_read}


@router.post("/workspaces/{workspace_id}/chat", status_code=201)
def send(workspace_id: uuid.UUID, body: NewMessage, request: Request, actor: Actor = Depends(current_actor),
         db: Session = Depends(get_db)):
    access = policy.require_write(db, actor.user, workspace_id)
    existing = db.scalar(select(ChatMessage).where(ChatMessage.author_id == actor.id,
                                                   ChatMessage.client_id == body.client_id))
    if existing is not None:
        if existing.workspace_id != workspace_id or existing.body != body.body:
            raise Conflict("client_id_reused", "This message ID was already used for different content.")
        return message_json(existing, users_by_id(db, [actor.id]))
    msg = ChatMessage(workspace_id=workspace_id, author_id=actor.id, body=body.body, client_id=body.client_id)
    db.add(msg)
    db.flush()
    notify.create(db, recipients=notify.mentioned_users(db, body.body, access.workspace, actor.id), kind="mention",
                  workspace_id=workspace_id, source_type="chat", source_id=msg.id, occurrence="created")
    _mark_read(db, actor.id, workspace_id, msg.seq)
    db.commit()
    payload = message_json(msg, users_by_id(db, [actor.id]))
    request.app.state.hub.publish(workspace_id, {"type": "chat.message", "message": payload})
    return payload


def _mark_read(db: Session, user_id, workspace_id, seq: int) -> None:
    stmt = insert(ChatRead).values(user_id=user_id, workspace_id=workspace_id, last_seq=seq)
    stmt = stmt.on_conflict_do_update(index_elements=["user_id", "workspace_id"],
                                      set_={"last_seq": stmt.excluded.last_seq},
                                      where=ChatRead.last_seq < stmt.excluded.last_seq)
    db.execute(stmt)


@router.post("/workspaces/{workspace_id}/chat/read")
def mark_read(workspace_id: uuid.UUID, body: ReadBody, actor: Actor = Depends(current_actor),
              db: Session = Depends(get_db)):
    policy.require_read(db, actor.user, workspace_id)
    _mark_read(db, actor.id, workspace_id, body.seq)
    db.commit()
    return {"ok": True}
