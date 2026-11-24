"""Board previews and published snapshots (S4).

``GET .../board/render`` draws a committed revision; ``POST .../board/snapshots`` publishes a
selected region at a committed revision as an immutable, destination-owned noticeboard post.
"""

from __future__ import annotations

import uuid
from types import SimpleNamespace

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import Response
from PIL import Image
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import audit, metrics, policy
from ..boardstate import render_png, state_at
from ..config import Settings
from ..deps import Actor, current_actor, get_db, get_settings
from ..errors import ApiError, Conflict, Invalid, NotFound
from ..identity_locks import lock_identity
from ..models import Asset, Post, Workspace
from ..reservations import check_original_capacity
from ..storage import AssetStore
from .board import _get_board, _hash

router = APIRouter(tags=["board"])

PNG_HEADERS = {
    "Cache-Control": "private, no-store",
    "X-Content-Type-Options": "nosniff",
    "Content-Security-Policy": "default-src 'none'; sandbox",
}


class Region(BaseModel):
    x: float
    y: float
    w: float = Field(gt=0)
    h: float = Field(gt=0)


class SnapshotBody(BaseModel):
    revision: int = Field(ge=0)
    region: Region
    destination_id: uuid.UUID
    summary: str = Field(min_length=1, max_length=2000)
    client_id: str = Field(min_length=8, max_length=64)
    # Required when the destination differs from the source: the destination ID the user confirmed.
    confirm_audience: uuid.UUID | None = None
    board_index: int = Field(default=0, ge=0, le=50)


def _image_loader(db: Session, store: AssetStore, workspace_id: uuid.UUID):
    def load(asset_id: uuid.UUID):
        asset = db.get(Asset, asset_id)
        # Only images owned by this board are rendered; anything else is skipped.
        if asset is None or asset.board_workspace_id != workspace_id or not asset.has_preview:
            return None
        try:
            return Image.open(store.path(asset.storage_key, preview=True))
        except (FileNotFoundError, OSError):
            return None

    return load


def _render(
    db: Session,
    request: Request,
    workspace_id: uuid.UUID,
    revision: int,
    region: Region,
    *,
    board_index: int = 0,
) -> bytes:
    board = _get_board(db, workspace_id, board_index)
    if board is None or not 0 <= revision <= board.revision:
        raise Invalid("invalid_revision", "That revision does not exist.")
    objects = state_at(db, board, revision)
    return render_png(
        objects,
        (region.x, region.y, region.w, region.h),
        _image_loader(db, request.app.state.assets, workspace_id),
    )


@router.get("/workspaces/{workspace_id}/board/render")
def render_preview(
    workspace_id: uuid.UUID,
    request: Request,
    revision: int,
    x: float,
    y: float,
    *,
    w: float = Query(gt=0),
    h: float = Query(gt=0),
    board_index: int = Query(default=0, ge=0, le=50),
    actor: Actor = Depends(current_actor),
    db: Session = Depends(get_db),
):
    """PNG of a region at a committed revision, for the publish preview."""
    policy.require_read(db, actor.user, workspace_id)
    png = _render(db, request, workspace_id, revision, Region(x=x, y=y, w=w, h=h), board_index=board_index)
    return Response(png, media_type="image/png", headers=PNG_HEADERS)


def snapshot_destinations(db: Session, actor: Actor, source: Workspace) -> list[Workspace]:
    """The source itself plus readable, writable ancestors in the organization tree."""
    out = [source]
    if source.kind == "org":
        parents = dict(
            db.execute(select(Workspace.id, Workspace.parent_id).where(Workspace.kind == "org")).all()
        )
        for anc in policy.ancestors(parents, source.id):
            access = policy.resolve(db, actor.user, anc)
            if access is not None and access.can_contribute:
                out.append(access.workspace)
    return out


@router.get("/workspaces/{workspace_id}/board/snapshot-destinations")
def list_destinations(
    workspace_id: uuid.UUID, actor: Actor = Depends(current_actor), db: Session = Depends(get_db)
):
    access = policy.require_read(db, actor.user, workspace_id)
    dests = snapshot_destinations(db, actor, access.workspace)
    return {
        "destinations": [
            {
                "id": str(w.id),
                "name": w.name,
                "same_workspace": w.id == workspace_id,
                "can_write": policy.resolve(db, actor.user, w.id).can_contribute,
            }
            for w in dests
        ]
    }


@router.post("/workspaces/{workspace_id}/board/snapshots", status_code=201)
def publish_snapshot(  # noqa: PLR0915 — ordered authorization and revision checks before the commit
    workspace_id: uuid.UUID,
    body: SnapshotBody,
    request: Request,
    *,
    actor: Actor = Depends(current_actor),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    identity = SimpleNamespace(id=actor.id, session=SimpleNamespace(id=actor.session.id))
    # Generated originals share the same user serialization as upload admission.
    # This synchronous endpoint already runs in a worker thread.
    lock_identity(db, identity, settings)
    # Fresh authorization on both ends at publish time.
    source = policy.require_read(db, actor.user, workspace_id).workspace
    intent_digest = _hash({"source": str(workspace_id), **body.model_dump(mode="json")})
    existing = db.scalar(select(Post).where(Post.author_id == actor.id, Post.client_id == body.client_id))
    if existing is not None:
        if (
            existing.source_request_digest != intent_digest
            or existing.source_workspace_id != workspace_id
            or existing.workspace_id != body.destination_id
            or existing.source_revision != body.revision
            or existing.body != body.summary
        ):
            raise Conflict("client_id_reused", "This request ID was already used for different content.")
        policy.require_read(db, actor.user, existing.workspace_id)
        return {"post_id": str(existing.id), "workspace_id": str(existing.workspace_id), "duplicate": True}
    allowed = {w.id for w in snapshot_destinations(db, actor, source)}
    if body.destination_id not in allowed:
        raise NotFound()
    dest = policy.require_contribute(db, actor.user, body.destination_id).workspace
    if dest.id not in (source.id, body.confirm_audience):
        raise Invalid(
            "confirmation_required", f"Confirm that everyone who can read {dest.name} will see this snapshot."
        )
    board_idx = getattr(body, "board_index", 0)
    png = _render(db, request, workspace_id, body.revision, body.region, board_index=board_idx)
    check_original_capacity(db, identity, settings, len(png))
    store: AssetStore = request.app.state.assets
    stored = store.save(png, "image/png")
    candidate_id = uuid.uuid4()
    commit_started = False
    try:
        # Time-based session expiry can pass while render/storage runs even
        # though revocation updates are serialized by the held row locks.
        lock_identity(db, identity, settings)
        post = Post(
            id=candidate_id,
            workspace_id=dest.id,
            author_id=actor.id,
            kind="discussion",
            body=body.summary,
            client_id=body.client_id,
            source_workspace_id=source.id,
            source_revision=body.revision,
            source_request_digest=intent_digest,
        )
        db.add(post)
        db.flush()
        db.add(
            Asset(
                owner_id=actor.id,
                storage_key=stored.storage_key,
                media_type="image/png",
                display_name=f"board-snapshot-r{body.revision}.png",
                size=stored.size,
                sha256=stored.sha256,
                has_preview=stored.has_preview,
                preview_size=stored.preview_size,
                preview_sha256=stored.preview_sha256,
                status="committed",
                post_id=post.id,
            )
        )
        audit.record(
            db,
            actor=actor.user,
            action="board.snapshot_publish",
            scope_type="workspace",
            scope_id=dest.id,
            target_id=post.id,
            source=source.id,
            revision=body.revision,
            broader=dest.id != source.id,
        )
        db.flush()
        # Counted by the commit itself: the outcome-unknown path below may never confirm it.
        metrics.count_workspace_on_commit(db, "posts.created", dest)
        lock_identity(db, identity, settings)
        commit_started = True
        db.commit()
    except Exception:
        db.rollback()
        if not commit_started:
            store.delete(stored.storage_key)
            raise
        confirmed = False
        try:
            with request.app.state.session_factory() as fresh:
                durable = fresh.get(Post, candidate_id)
                if durable is not None:
                    user = lock_identity(fresh, identity, settings)
                    policy.require_read(fresh, user, workspace_id)
                    policy.require_read(fresh, user, body.destination_id)
                    confirmed = True
        except ApiError:
            raise
        except Exception:  # noqa: BLE001, S110 — any failure while confirming leaves the outcome unknown
            pass
        if not confirmed:
            raise ApiError(
                "snapshot_commit_unknown",
                "Snapshot outcome is uncertain. Storage was retained for inspection; check the noticeboard "
                "before retrying.",
                status=503,
            ) from None
    destination_id = body.destination_id
    request.app.state.hub.publish(
        destination_id, {"type": "noticeboard.changed", "workspace_id": str(destination_id)}
    )
    return {"post_id": str(candidate_id), "workspace_id": str(destination_id), "duplicate": False}
