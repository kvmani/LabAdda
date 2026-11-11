"""Noticeboard: posts, replies, pins, official notices, upcoming and search (S3)."""

from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import audit, notify, policy
from ..config import Settings
from ..deps import Actor, current_actor, get_db, get_settings
from ..errors import Conflict, Forbidden, Invalid, NotFound
from ..models import Asset, ChatMessage, Post, Workspace
from ..security import utcnow
from ..serialize import iso, post_json, user_brief, users_by_id

router = APIRouter(tags=["noticeboard"])
MAX_BODY = 10_000


class NewPost(BaseModel):
    body: str = Field(min_length=1, max_length=MAX_BODY)
    kind: str = "discussion"
    due_at: datetime | None = None
    remind_at: datetime | None = None
    attachment_ids: list[uuid.UUID] = Field(default_factory=list)
    client_id: str | None = Field(default=None, max_length=64)


class NewReply(BaseModel):
    body: str = Field(min_length=1, max_length=MAX_BODY)
    client_id: str | None = Field(default=None, max_length=64)


class PostPatch(BaseModel):
    body: str | None = Field(default=None, min_length=1, max_length=MAX_BODY)
    due_at: datetime | None = None
    remind_at: datetime | None = None
    update_schedule: bool = False


class PinBody(BaseModel):
    pinned: bool


def _hub(request: Request):
    return request.app.state.hub


def _check_schedule(due_at, remind_at):
    for value in (due_at, remind_at):
        if value is not None and value.tzinfo is None:
            raise Invalid("timezone_required", "Times must include a UTC offset.")
    if due_at and remind_at and remind_at > due_at:
        raise Invalid("remind_after_due", "The reminder must be at or before the due time.")


def _render(db: Session, posts: list[Post], actor: Actor, can_moderate: bool, base: str) -> list[dict]:
    if not posts:
        return []
    ids = [p.id for p in posts]
    replies = db.scalars(
        select(Post).where(Post.parent_id.in_(ids), Post.deleted_at.is_(None)).order_by(Post.seq)
    ).all()
    all_ids = ids + [r.id for r in replies]
    assets: dict[uuid.UUID, list[Asset]] = {}
    for a in db.scalars(
        select(Asset)
        .where(Asset.post_id.in_(all_ids), Asset.status == "committed")
        .order_by(Asset.created_at)
    ):
        assets.setdefault(a.post_id, []).append(a)
    authors = users_by_id(db, [p.author_id for p in posts] + [r.author_id for r in replies])
    readable = policy.readable_workspace_ids(db, actor.user)
    sources = {p.source_workspace_id for p in posts if p.source_workspace_id}
    source_names = (
        dict(db.execute(select(Workspace.id, Workspace.name).where(Workspace.id.in_(sources))).all())
        if sources
        else {}
    )

    def snapshot_info(p: Post) -> dict | None:
        if p.source_workspace_id is None:
            return None
        # Name the source only to readers who can see it; others just see a fixed copy.
        visible = p.source_workspace_id in readable
        return {
            "source_revision": p.source_revision,
            "source_name": source_names.get(p.source_workspace_id) if visible else None,
            "source_workspace_id": str(p.source_workspace_id) if visible else None,
        }

    by_parent: dict[uuid.UUID, list[dict]] = {}
    for r in replies:
        by_parent.setdefault(r.parent_id, []).append(
            post_json(r, authors, assets.get(r.id, []), base, actor_id=actor.id, can_moderate=can_moderate)
        )
    return [
        {
            **post_json(
                p, authors, assets.get(p.id, []), base, by_parent.get(p.id, []), actor.id, can_moderate
            ),
            "snapshot": snapshot_info(p),
        }
        for p in posts
    ]


def _load_post(db: Session, actor: Actor, post_id: uuid.UUID):
    post = db.get(Post, post_id)
    if post is None or post.deleted_at is not None:
        raise NotFound()
    access = policy.resolve(db, actor.user, post.workspace_id)
    if access is None:
        raise NotFound()
    return post, access


def _existing_by_client_id(
    db: Session, actor: Actor, client_id: str | None, workspace_id, body: str, parent_id=None
):
    if not client_id:
        return None
    existing = db.scalar(select(Post).where(Post.author_id == actor.id, Post.client_id == client_id))
    if existing is None:
        return None
    if existing.workspace_id != workspace_id or existing.body != body or existing.parent_id != parent_id:
        raise Conflict("client_id_reused", "This request ID was already used for different content.")
    return existing


@router.get("/workspaces/{workspace_id}/posts")
def list_posts(
    workspace_id: uuid.UUID,
    before: int | None = None,
    limit: int = Query(default=20, ge=1, le=50),
    actor: Actor = Depends(current_actor),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    access = policy.require_read(db, actor.user, workspace_id)
    top = (Post.workspace_id == workspace_id) & Post.parent_id.is_(None) & Post.deleted_at.is_(None)
    pinned = []
    if before is None:
        pinned = db.scalars(select(Post).where(top, Post.pinned.is_(True)).order_by(Post.seq.desc())).all()
    stmt = select(Post).where(top, Post.pinned.is_(False))
    if before is not None:
        stmt = stmt.where(Post.seq < before)
    feed = db.scalars(stmt.order_by(Post.seq.desc()).limit(limit + 1)).all()
    more = len(feed) > limit
    feed = feed[:limit]
    base = settings.api_prefix
    return {
        "pinned": _render(db, list(pinned), actor, access.can_moderate, base),
        "posts": _render(db, list(feed), actor, access.can_moderate, base),
        "next_before": feed[-1].seq if more and feed else None,
    }


@router.post("/workspaces/{workspace_id}/posts", status_code=201)
def create_post(
    workspace_id: uuid.UUID,
    body: NewPost,
    request: Request,
    actor: Actor = Depends(current_actor),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    access = policy.require_write(db, actor.user, workspace_id)
    if body.kind not in ("discussion", "official"):
        raise Invalid("invalid_kind", "Kind must be discussion or official.")
    if body.kind == "official" and not access.can_moderate:
        raise Forbidden("steward_required", "Only a steward can issue an official notice.")
    _check_schedule(body.due_at, body.remind_at)
    existing = _existing_by_client_id(db, actor, body.client_id, workspace_id, body.body)
    if existing is not None:
        return _render(db, [existing], actor, access.can_moderate, settings.api_prefix)[0]
    if len(set(body.attachment_ids)) > settings.max_attachments:
        raise Invalid("too_many_attachments", f"Attach up to {settings.max_attachments} files.")
    assets = []
    if body.attachment_ids:
        assets = db.scalars(
            select(Asset).where(Asset.id.in_(set(body.attachment_ids))).with_for_update()
        ).all()
        if len(assets) != len(set(body.attachment_ids)) or any(
            a.owner_id != actor.id or a.status != "provisional" for a in assets
        ):
            raise Invalid("invalid_attachment", "An attachment is missing or already used. Upload it again.")
    post = Post(
        workspace_id=workspace_id,
        author_id=actor.id,
        kind=body.kind,
        body=body.body,
        due_at=body.due_at,
        remind_at=body.remind_at,
        client_id=body.client_id,
    )
    db.add(post)
    db.flush()
    for a in assets:
        a.status = "committed"
        a.post_id = post.id
    ws = access.workspace
    if body.kind == "official":
        recipients = policy.eligible_reader_ids(db, ws) - {actor.id}
        notify.create(
            db,
            recipients=recipients,
            kind="official",
            workspace_id=ws.id,
            source_type="post",
            source_id=post.id,
            occurrence="created",
        )
    notify.create(
        db,
        recipients=notify.mentioned_users(db, body.body, ws, actor.id),
        kind="mention",
        workspace_id=ws.id,
        source_type="post",
        source_id=post.id,
        occurrence="created",
    )
    db.commit()
    _hub(request).publish(ws.id, {"type": "noticeboard.changed", "workspace_id": str(ws.id)})
    return _render(db, [post], actor, access.can_moderate, settings.api_prefix)[0]


@router.post("/posts/{post_id}/replies", status_code=201)
def reply(
    post_id: uuid.UUID,
    body: NewReply,
    request: Request,
    actor: Actor = Depends(current_actor),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    parent, _ = _load_post(db, actor, post_id)
    if parent.parent_id is not None:
        raise Invalid("nested_reply", "Reply to the original post.")
    access = policy.require_write(db, actor.user, parent.workspace_id)
    existing = _existing_by_client_id(db, actor, body.client_id, parent.workspace_id, body.body, parent.id)
    if existing is None:
        existing = Post(
            workspace_id=parent.workspace_id,
            parent_id=parent.id,
            author_id=actor.id,
            body=body.body,
            client_id=body.client_id,
        )
        db.add(existing)
        db.flush()
        notify.create(
            db,
            recipients=notify.mentioned_users(db, body.body, access.workspace, actor.id),
            kind="mention",
            workspace_id=parent.workspace_id,
            source_type="post",
            source_id=existing.id,
            occurrence="created",
        )
        db.commit()
        _hub(request).publish(
            parent.workspace_id, {"type": "noticeboard.changed", "workspace_id": str(parent.workspace_id)}
        )
    return _render(db, [existing], actor, access.can_moderate, settings.api_prefix)[0]


@router.patch("/posts/{post_id}")
def edit_post(
    post_id: uuid.UUID,
    body: PostPatch,
    request: Request,
    actor: Actor = Depends(current_actor),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    post, _ = _load_post(db, actor, post_id)
    access = policy.require_write(db, actor.user, post.workspace_id)
    if post.author_id != actor.id:
        raise Forbidden("author_required", "Only the author can edit this post.")
    if body.body is not None:
        post.body = body.body
    if body.update_schedule:
        _check_schedule(body.due_at, body.remind_at)
        if body.remind_at != post.remind_at:
            post.reminder_processed_at = None  # new occurrence gets its own uniqueness key
        post.due_at, post.remind_at = body.due_at, body.remind_at
    post.edited_at = utcnow()
    db.commit()
    _hub(request).publish(
        post.workspace_id, {"type": "noticeboard.changed", "workspace_id": str(post.workspace_id)}
    )
    return _render(db, [post], actor, access.can_moderate, settings.api_prefix)[0]


@router.delete("/posts/{post_id}")
def delete_post(
    post_id: uuid.UUID,
    request: Request,
    reason: str | None = Query(default=None, max_length=500),
    actor: Actor = Depends(current_actor),
    db: Session = Depends(get_db),
):
    post, access = _load_post(db, actor, post_id)
    is_author = post.author_id == actor.id
    if is_author:
        policy.require_write(db, actor.user, post.workspace_id)
    elif not access.can_moderate:
        raise Forbidden("author_required", "Only the author or a steward can remove this post.")
    elif not reason or not reason.strip():
        raise Invalid("reason_required", "Give a reason for removing someone else's post.")
    post.deleted_at = utcnow()
    post.removed_by = actor.id
    post.removed_reason = None if is_author else reason.strip()
    if not is_author:
        audit.record(
            db,
            actor=actor.user,
            action="post.moderate_remove",
            scope_type="workspace",
            scope_id=post.workspace_id,
            target_id=post.id,
            reason=reason.strip(),
        )
    db.commit()
    _hub(request).publish(
        post.workspace_id, {"type": "noticeboard.changed", "workspace_id": str(post.workspace_id)}
    )
    return {"ok": True}


@router.post("/posts/{post_id}/pin")
def pin_post(
    post_id: uuid.UUID,
    body: PinBody,
    request: Request,
    actor: Actor = Depends(current_actor),
    db: Session = Depends(get_db),
):
    post, access = _load_post(db, actor, post_id)
    if not access.can_moderate:
        raise Forbidden("steward_required", "Only a steward can pin notices.")
    if access.workspace.archived:
        raise Forbidden("workspace_archived", "This workspace is archived and read-only.")
    if post.parent_id is not None:
        raise Invalid("pin_reply", "Only original posts can be pinned.")
    post.pinned = body.pinned
    audit.record(
        db,
        actor=actor.user,
        action="post.pin" if body.pinned else "post.unpin",
        scope_type="workspace",
        scope_id=post.workspace_id,
        target_id=post.id,
    )
    db.commit()
    _hub(request).publish(
        post.workspace_id, {"type": "noticeboard.changed", "workspace_id": str(post.workspace_id)}
    )
    return {"ok": True, "pinned": post.pinned}


@router.get("/workspaces/{workspace_id}/upcoming")
def upcoming(
    workspace_id: uuid.UUID,
    limit: int = Query(default=10, le=50),
    actor: Actor = Depends(current_actor),
    db: Session = Depends(get_db),
):
    policy.require_read(db, actor.user, workspace_id)
    rows = db.scalars(
        select(Post)
        .where(
            Post.workspace_id == workspace_id,
            Post.deleted_at.is_(None),
            Post.due_at.is_not(None),
            Post.due_at >= utcnow(),
        )
        .order_by(Post.due_at)
        .limit(limit)
    ).all()
    return {
        "items": [
            {
                "id": str(p.id),
                "source": "post",
                "title": p.body[:120],
                "due_at": iso(p.due_at),
                "remind_at": iso(p.remind_at),
                "kind": p.kind,
            }
            for p in rows
        ]
    }


@router.get("/workspaces/{workspace_id}/search")
def search(
    workspace_id: uuid.UUID,
    q: str = Query(min_length=2, max_length=100),
    limit: int = Query(default=20, le=50),
    actor: Actor = Depends(current_actor),
    db: Session = Depends(get_db),
):
    """Workspace-local text search over posts and chat. Never crosses scope."""
    policy.require_read(db, actor.user, workspace_id)
    term = "%" + q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
    post_filter = (
        (Post.workspace_id == workspace_id) & Post.deleted_at.is_(None) & Post.body.ilike(term, escape="\\")
    )
    chat_filter = (ChatMessage.workspace_id == workspace_id) & ChatMessage.body.ilike(term, escape="\\")
    posts = db.scalars(select(Post).where(post_filter).order_by(Post.seq.desc()).limit(limit)).all()
    chats = db.scalars(
        select(ChatMessage).where(chat_filter).order_by(ChatMessage.seq.desc()).limit(limit)
    ).all()
    authors = users_by_id(db, [p.author_id for p in posts] + [c.author_id for c in chats])
    return {
        "counts": {
            "posts": db.scalar(select(func.count()).select_from(Post).where(post_filter)) or 0,
            "chat": db.scalar(select(func.count()).select_from(ChatMessage).where(chat_filter)) or 0,
        },
        "posts": [
            {
                "id": str(p.id),
                "parent_id": str(p.parent_id) if p.parent_id else None,
                "body": p.body[:300],
                "created_at": iso(p.created_at),
                "author": user_brief(authors.get(p.author_id)),
            }
            for p in posts
        ],
        "chat": [
            {
                "id": str(c.id),
                "seq": c.seq,
                "body": c.body[:300],
                "created_at": iso(c.created_at),
                "author": user_brief(authors.get(c.author_id)),
            }
            for c in chats
        ],
    }
