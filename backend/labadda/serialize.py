"""JSON shapes shared by routers. Keep these in step with docs/API.md."""

from __future__ import annotations

import uuid
from collections.abc import Iterable
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Asset, Post, User, Workspace
from .policy import Access


def iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is not None:
        return value.astimezone(UTC).isoformat()
    return value.isoformat()


def user_brief(user: User | None) -> dict | None:
    if user is None:
        return None
    return {
        "id": str(user.id),
        "username": user.username,
        "display_name": user.display_name,
        "is_active": user.is_active,
    }


def users_by_id(db: Session, ids: Iterable[uuid.UUID]) -> dict[uuid.UUID, User]:
    ids = {i for i in ids if i}
    if not ids:
        return {}
    return {u.id: u for u in db.scalars(select(User).where(User.id.in_(ids)))}


def workspace_json(ws: Workspace, access: Access | None = None) -> dict:
    data = {
        "id": str(ws.id),
        "kind": ws.kind,
        "name": ws.name,
        "code": ws.code,
        "level": ws.level,
        "description": ws.description,
        "parent_id": str(ws.parent_id) if ws.parent_id else None,
        "archived": ws.archived,
        "posting_policy": ws.posting_policy,
    }
    if access is not None:
        data.update(
            role=access.direct_role,
            inherited=access.inherited,
            can_write=access.can_write,
            can_moderate=access.can_moderate,
        )
    return data


def asset_json(asset: Asset, base: str) -> dict:
    return {
        "id": str(asset.id),
        "display_name": asset.display_name,
        "media_type": asset.media_type,
        "size": asset.size,
        "status": asset.status,
        "url": f"{base}/files/{asset.id}",
        "preview_url": f"{base}/files/{asset.id}/preview" if asset.has_preview else None,
    }


def post_json(
    post: Post,
    authors: dict,
    assets: list[Asset],
    base: str,
    *,
    replies: list[dict] | None = None,
    actor_id=None,
    can_moderate: bool = False,
) -> dict:
    removed = post.deleted_at is not None
    return {
        "id": str(post.id),
        "seq": post.seq,
        "workspace_id": str(post.workspace_id),
        "parent_id": str(post.parent_id) if post.parent_id else None,
        "kind": post.kind,
        "body": "" if removed else post.body,
        "removed": removed,
        "removed_by_moderator": removed and post.removed_by is not None and post.removed_by != post.author_id,
        "pinned": post.pinned,
        "due_at": iso(post.due_at),
        "remind_at": iso(post.remind_at),
        "created_at": iso(post.created_at),
        "edited_at": iso(post.edited_at),
        "author": user_brief(authors.get(post.author_id)),
        "attachments": [] if removed else [asset_json(a, base) for a in assets],
        "replies": replies if replies is not None else [],
        "can_edit": not removed and actor_id == post.author_id,
        "can_remove": not removed and (actor_id == post.author_id or can_moderate),
    }
