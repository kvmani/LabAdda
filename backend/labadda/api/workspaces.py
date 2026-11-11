"""Workspace navigation, members, posting policy and home selection (S2, S3)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import audit, policy
from ..deps import Actor, current_actor, get_db
from ..errors import Forbidden, Invalid
from ..models import ChatMessage, ChatRead, Membership, User, Workspace
from ..serialize import user_brief, workspace_json

router = APIRouter(tags=["workspaces"])


def _unread_chat(db: Session, user_id, ws_ids: list[uuid.UUID]) -> dict[uuid.UUID, int]:
    if not ws_ids:
        return {}
    reads = dict(
        db.execute(
            select(ChatRead.workspace_id, ChatRead.last_seq).where(
                ChatRead.user_id == user_id, ChatRead.workspace_id.in_(ws_ids)
            )
        ).all()
    )
    out = {}
    for ws_id in ws_ids:
        out[ws_id] = (
            db.scalar(
                select(func.count())
                .select_from(ChatMessage)
                .where(
                    ChatMessage.workspace_id == ws_id,
                    ChatMessage.seq > reads.get(ws_id, 0),
                    ChatMessage.author_id != user_id,
                )
            )
            or 0
        )
    return out


@router.get("/workspaces")
def list_workspaces(actor: Actor = Depends(current_actor), db: Session = Depends(get_db)):
    readable = policy.readable_workspace_ids(db, actor.user)
    rows = db.scalars(select(Workspace).where(Workspace.id.in_(list(readable)))).all() if readable else []
    unread = _unread_chat(db, actor.id, [w.id for w in rows])
    items = []
    for ws in sorted(rows, key=lambda w: (w.kind != "org", w.name.lower())):
        access = policy.resolve(db, actor.user, ws.id)
        items.append({**workspace_json(ws, access), "unread_chat": unread.get(ws.id, 0)})
    home = actor.user.home_workspace_id
    direct = [i for i in items if i["role"] is not None]
    if home is None or str(home) not in {i["id"] for i in direct}:
        # Home lost or unset: fall back to an accessible direct workspace.
        home = direct[0]["id"] if direct else None
    return {"workspaces": items, "home_workspace_id": str(home) if home else None}


@router.get("/workspaces/{workspace_id}")
def get_workspace(
    workspace_id: uuid.UUID, actor: Actor = Depends(current_actor), db: Session = Depends(get_db)
):
    access = policy.require_read(db, actor.user, workspace_id)
    readable = policy.readable_workspace_ids(db, actor.user)
    trail = []
    if access.workspace.kind == "org":
        parents = dict(
            db.execute(select(Workspace.id, Workspace.parent_id).where(Workspace.kind == "org")).all()
        )
        for anc in policy.ancestors(parents, workspace_id):
            if anc in readable:
                trail.append(anc)
    names = (
        dict(db.execute(select(Workspace.id, Workspace.name).where(Workspace.id.in_(trail))).all())
        if trail
        else {}
    )
    return {
        **workspace_json(access.workspace, access),
        "ancestors": [{"id": str(a), "name": names[a]} for a in trail],
    }


@router.get("/workspaces/{workspace_id}/members")
def list_members(
    workspace_id: uuid.UUID, actor: Actor = Depends(current_actor), db: Session = Depends(get_db)
):
    policy.require_read(db, actor.user, workspace_id)
    rows = db.execute(
        select(Membership, User)
        .join(User, User.id == Membership.user_id)
        .where(Membership.workspace_id == workspace_id)
        .order_by(User.display_name)
    ).all()
    return {"members": [{**user_brief(u), "role": m.role} for m, u in rows]}


class PolicyBody(BaseModel):
    posting_policy: str


@router.patch("/workspaces/{workspace_id}/policy")
def set_policy(
    workspace_id: uuid.UUID,
    body: PolicyBody,
    actor: Actor = Depends(current_actor),
    db: Session = Depends(get_db),
):
    access = policy.require_moderate(db, actor.user, workspace_id)
    if body.posting_policy not in ("open", "read_only"):
        raise Invalid("invalid_policy", "Posting policy must be open or read_only.")
    if access.workspace.archived:
        raise Forbidden("workspace_archived", "This workspace is archived and read-only.")
    ws = db.get(Workspace, workspace_id)
    ws.posting_policy = body.posting_policy
    audit.record(
        db,
        actor=actor.user,
        action="workspace.posting_policy",
        scope_type="workspace",
        scope_id=ws.id,
        policy=body.posting_policy,
    )
    db.commit()
    return workspace_json(ws, policy.resolve(db, actor.user, ws.id))


class HomeBody(BaseModel):
    workspace_id: uuid.UUID | None


@router.put("/me/home")
def set_home(
    body: HomeBody, request: Request, actor: Actor = Depends(current_actor), db: Session = Depends(get_db)
):
    user = db.get(User, actor.user.id)
    if body.workspace_id is not None:
        grants = policy.direct_grants(db, user.id)
        if body.workspace_id not in grants:
            raise Invalid("home_not_direct", "Home must be a workspace you belong to directly.")
    user.home_workspace_id = body.workspace_id
    db.commit()
    return {"home_workspace_id": str(user.home_workspace_id) if user.home_workspace_id else None}
