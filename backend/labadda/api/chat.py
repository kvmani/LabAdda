"""Workspace chat stream with idempotent sends and cursor replay (S3)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from .. import notify, policy
from ..deps import Actor, current_actor, get_db, get_settings
from ..errors import Conflict, Invalid, NotFound
from ..models import ChatMessage, ChatRead, Workspace
from ..serialize import iso, user_brief, users_by_id
from ..identity_locks import lock_identity
from .todos import _actor, _scope, _scope_locks

router = APIRouter(tags=["chat"])


class NewMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")
    parent_id: uuid.UUID | None = None
    body: str = Field(min_length=1, max_length=4000)
    client_id: str = Field(min_length=8, max_length=64)


class ReadBody(BaseModel):
    seq: int


def message_json(m: ChatMessage, authors: dict) -> dict:
    return {"id": str(m.id), "seq": m.seq, "workspace_id": str(m.workspace_id), "body": m.body,
            "parent_id": str(m.parent_id) if m.parent_id else None, "client_id": m.client_id, "created_at": iso(m.created_at), "author": user_brief(authors.get(m.author_id))}


@router.get("/workspaces/{workspace_id}/chat")
def history(workspace_id: uuid.UUID, request: Request, before: int | None = None, after: int | None = None,
            limit: int = Query(default=50, ge=1, le=200), actor: Actor = Depends(current_actor),
            db: Session = Depends(get_db)):
    user = _actor(request, actor, db)
    policy.require_read(db, user, workspace_id)
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
    result = {"messages": [message_json(m, authors) for m in rows], "has_more": more, "last_read_seq": last_read}
    policy.require_read(db, _actor(request, actor, db), workspace_id)
    return result


@router.post("/workspaces/{workspace_id}/chat", status_code=201)
def send(workspace_id: uuid.UUID, body: NewMessage, request: Request, actor: Actor = Depends(current_actor),
         db: Session = Depends(get_db)):
    user = _actor(request, actor, db, True)
    access = _scope(db, user, workspace_id, True)
    # Serialize allocation/commit per workspace; other authors cannot commit a
    # higher stream sequence while an earlier message is still uncommitted.
    db.execute(select(Workspace.id).where(Workspace.id == workspace_id).with_for_update(key_share=True))
    if body.parent_id:
        _root(db, user, workspace_id, body.parent_id)
    existing = db.scalar(select(ChatMessage).where(ChatMessage.author_id == actor.id,
                                                   ChatMessage.client_id == body.client_id))
    if existing is not None:
        if existing.workspace_id != workspace_id or existing.body != body.body or existing.parent_id != body.parent_id:
            raise Conflict("client_id_reused", "This message ID was already used for different content.")
        lock_identity(db, actor, get_settings(request))
        return message_json(existing, users_by_id(db, [actor.id]))
    msg = ChatMessage(workspace_id=workspace_id, author_id=actor.id, body=body.body, client_id=body.client_id, parent_id=body.parent_id)
    db.add(msg)
    db.flush()
    notify.create(db, recipients=notify.mentioned_users(db, body.body, access.workspace, actor.id), kind="mention",
                  workspace_id=workspace_id, source_type="chat", source_id=msg.id, occurrence="created")
    _mark_read(db, actor.id, workspace_id, msg.seq)
    lock_identity(db, actor, get_settings(request))
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
def mark_read(workspace_id: uuid.UUID, body: ReadBody, request: Request, actor: Actor = Depends(current_actor),
              db: Session = Depends(get_db)):
    user = _actor(request, actor, db, True)
    _scope_locks(db, workspace_id)
    policy.require_read(db, user, workspace_id)
    _mark_read(db, actor.id, workspace_id, body.seq)
    lock_identity(db, actor, get_settings(request))
    db.commit()
    return {"ok": True}


def _root(db, user, workspace_id, message_id):
    policy.require_read(db, user, workspace_id)
    row=db.get(ChatMessage,message_id)
    if row is None or row.workspace_id!=workspace_id:
        raise NotFound()
    if row.parent_id is not None:
        raise Invalid('thread_root_required','Reply to the original message, not another reply.')
    return row


@router.get('/workspaces/{workspace_id}/chat/{message_id}/replies')
def replies(workspace_id:uuid.UUID,message_id:uuid.UUID,request:Request,
            before:int|None=Query(default=None,ge=1),limit:int=Query(default=25,ge=1,le=100),
            actor:Actor=Depends(current_actor),db:Session=Depends(get_db)):
    user=_actor(request,actor,db)
    root=_root(db,user,workspace_id,message_id)
    query=select(ChatMessage).where(ChatMessage.workspace_id==workspace_id,ChatMessage.parent_id==message_id)
    if before is not None:query=query.where(ChatMessage.seq<before)
    rows=db.scalars(query.order_by(ChatMessage.seq.desc()).limit(limit+1)).all()
    authors=users_by_id(db,[root.author_id,*[r.author_id for r in rows]])
    result={'root':message_json(root,authors),'messages':[message_json(r,authors) for r in reversed(rows[:limit])],
            'next_before':rows[limit-1].seq if len(rows)>limit else None}
    _root(db,_actor(request,actor,db),workspace_id,message_id)
    return result
