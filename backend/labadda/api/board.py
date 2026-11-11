"""Persistent workspace whiteboard with sequenced, idempotent operations (S3, S4).

State is the fold of committed operations in the current epoch, starting
from the latest compacted snapshot. Each operation has a client-chosen
``op_id``; identity is (workspace, epoch, actor, op_id). A retry with the same
payload returns the committed result; reuse with a different payload fails
with 409. A restore starts a new epoch, so pending operations against the old
epoch are rejected. ``POST .../board/snapshots`` publishes a selected region
at a committed revision as an immutable, destination-owned noticeboard post.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from types import SimpleNamespace

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import Response
from PIL import Image
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from .. import audit, policy
from ..boardstate import epoch_ops, latest_snapshot, render_png, state_at, state_cache, undo_target, with_op
from ..charges import charge_board_object, recharge_board
from ..config import Settings
from ..deps import Actor, board_actor, current_actor, get_db, get_settings
from ..errors import ApiError, Conflict, Forbidden, Invalid, NotFound
from ..identity_locks import lock_identity
from ..models import Asset, Board, BoardOp, Post, Workspace
from ..reservations import check_original_capacity
from ..serialize import iso
from ..storage import AssetStore

router = APIRouter(tags=["board"])
MAX_POINTS = 4000
MAX_TEXT = 1000
MAX_IMAGE_SIDE = 4000
COLORS = {
    "#1f2933",
    "#c62828",
    "#1565c0",
    "#2e7d32",
    "#ef6c00",
    "#6a1b9a",
    "#fff59d",
    "#b3e5fc",
    "#c8e6c9",
    "#ffccbc",
}
PNG_HEADERS = {
    "Cache-Control": "private, no-store",
    "X-Content-Type-Options": "nosniff",
    "Content-Security-Policy": "default-src 'none'; sandbox",
}


class OpBody(BaseModel):
    op_id: str = Field(min_length=8, max_length=64)
    epoch: int
    type: str
    object_id: str | None = Field(default=None, max_length=64)
    payload: dict = Field(default_factory=dict)
    base_revision: int | None = None  # for move: object revision the client edited from


class RestoreBody(BaseModel):
    revision: int = Field(ge=0)
    reason: str | None = Field(default=None, max_length=500)


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


def _hash(payload: dict) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def op_json(op: BoardOp) -> dict:
    return {
        "revision": op.revision,
        "epoch": op.epoch,
        "op_id": op.op_id,
        "actor_id": str(op.actor_id),
        "type": op.op_type,
        "object_id": op.object_id,
        "payload": op.payload,
        "created_at": iso(op.created_at),
    }


def _ensure_board(db: Session, workspace_id: uuid.UUID) -> Board:
    # A new board is empty, so its charges are trivially complete for epoch 1.
    db.execute(
        insert(Board)
        .values(workspace_id=workspace_id, epoch=1, revision=0, base_revision=0, charges_epoch=1)
        .on_conflict_do_nothing(index_elements=["workspace_id"])
    )
    return db.scalar(select(Board).where(Board.workspace_id == workspace_id).with_for_update())


def _num(v, lo=-1e6, hi=1e6) -> float:
    if not isinstance(v, (int, float)) or isinstance(v, bool) or not lo <= v <= hi:
        raise Invalid("invalid_board_op", "Board coordinates are out of range.")
    return float(v)


def _validate_add(db: Session, actor: Actor, workspace_id: uuid.UUID, payload: dict) -> dict:
    kind = payload.get("kind")
    data = payload.get("data") or {}
    if kind == "image":
        try:
            asset_id = uuid.UUID(str(data.get("asset_id")))
        except ValueError:
            raise Invalid("invalid_board_op", "Unknown image.") from None
        asset = db.get(Asset, asset_id, with_for_update=True)
        reusable = asset is not None and asset.board_workspace_id == workspace_id
        fresh = asset is not None and asset.status == "provisional" and asset.owner_id == actor.id
        if not (reusable or fresh) or not asset.media_type.startswith("image/"):
            raise Invalid("invalid_board_op", "Upload a PNG or JPEG image before placing it on the board.")
        if fresh:
            asset.status, asset.board_workspace_id = "committed", workspace_id
        return {
            "kind": kind,
            "data": {
                "x": _num(data.get("x")),
                "y": _num(data.get("y")),
                "w": _num(data.get("w"), 1, MAX_IMAGE_SIDE),
                "h": _num(data.get("h"), 1, MAX_IMAGE_SIDE),
                "asset_id": str(asset_id),
            },
        }
    color = data.get("color", "#1f2933")
    if color not in COLORS:
        raise Invalid("invalid_board_op", "Unsupported colour.")
    if kind == "stroke":
        pts = data.get("points")
        if not isinstance(pts, list) or not 1 <= len(pts) <= MAX_POINTS:
            raise Invalid("invalid_board_op", "A stroke needs between 1 and 4000 points.")
        points = [[round(_num(p[0]), 1), round(_num(p[1]), 1)] for p in pts]
        width = _num(data.get("width", 3), 1, 64)
        return {"kind": kind, "data": {"points": points, "color": color, "width": width}}
    if kind in ("text", "sticky"):
        text = data.get("text")
        if not isinstance(text, str) or not text.strip() or len(text) > MAX_TEXT:
            raise Invalid("invalid_board_op", "Text must be 1-1000 characters.")
        return {
            "kind": kind,
            "data": {"x": _num(data.get("x")), "y": _num(data.get("y")), "text": text, "color": color},
        }
    raise Invalid("invalid_board_op", "Unknown board object kind.")


@router.get("/workspaces/{workspace_id}/board")
def get_board(
    workspace_id: uuid.UUID,
    epoch: int | None = None,
    after: int | None = None,
    actor: Actor = Depends(board_actor),
    db: Session = Depends(get_db),
):
    access = policy.require_read(db, actor.user, workspace_id)
    board = db.get(Board, workspace_id)
    current_epoch, revision, base = (board.epoch, board.revision, board.base_revision) if board else (1, 0, 0)
    # Replay is possible only within the epoch and above the compacted base.
    replay = epoch == current_epoch and after is not None and after >= base
    snapshot = None
    if not replay and base > 0:
        snap = latest_snapshot(db, workspace_id, current_epoch, upto=base)
        if snap is not None:
            snapshot = {"revision": snap.revision, "objects": snap.state}
    ops = epoch_ops(db, workspace_id, current_epoch, after=after if replay else base)
    return {
        "epoch": current_epoch,
        "revision": revision,
        "base_revision": base,
        "reset": not replay,
        "snapshot": snapshot,
        "ops": [op_json(o) for o in ops],
        "can_write": access.can_write,
        "can_moderate": access.can_moderate and not actor.is_panel,
    }


@router.post("/workspaces/{workspace_id}/board/ops")
def submit_op(
    workspace_id: uuid.UUID,
    body: OpBody,
    request: Request,
    actor: Actor = Depends(board_actor),
    db: Session = Depends(get_db),
):
    policy.require_write(db, actor.user, workspace_id)
    if actor.is_panel and body.type == "add" and (body.payload or {}).get("kind") == "image":
        # Shared panels have no file picker; images are placed from a desktop session.
        raise Forbidden("panel_not_allowed", "Images can be added from a desktop session.")
    board = _ensure_board(db, workspace_id)  # row lock serializes sequencing per board
    intent = {
        "type": body.type,
        "object_id": body.object_id,
        "payload": body.payload,
        "base_revision": body.base_revision,
    }
    intent_hash = _hash(intent)
    existing = db.scalar(
        select(BoardOp).where(
            BoardOp.workspace_id == workspace_id,
            BoardOp.epoch == body.epoch,
            BoardOp.actor_id == actor.id,
            BoardOp.op_id == body.op_id,
        )
    )
    if existing is not None:
        db.rollback()
        if existing.payload_hash != intent_hash:
            raise Conflict("op_id_reused", "This operation ID was already used for a different change.")
        return {"committed": op_json(existing), "duplicate": True}
    if body.epoch != board.epoch:
        db.rollback()
        raise Conflict("stale_epoch", "The board was restored. Reload to continue.")
    objects = state_cache.objects(db, board)  # read-only here; advanced only after commit
    if body.type == "add":
        object_id = body.object_id or ""
        if not object_id or object_id in objects:
            raise Conflict("object_exists", "That board object already exists.")
        payload = _validate_add(db, actor, workspace_id, body.payload)
        payload["author"] = str(actor.id)
    elif body.type in ("erase", "move"):
        obj = objects.get(body.object_id or "")
        if obj is None or not obj["alive"]:
            raise Conflict("object_gone", "That item was already removed.")
        if body.type == "move":
            if body.base_revision is not None and obj["rev"] > body.base_revision:
                raise Conflict("stale_object", "Someone else changed this item first.")
            payload = {"dx": _num(body.payload.get("dx")), "dy": _num(body.payload.get("dy"))}
        else:
            payload = {}
        object_id = body.object_id
    elif body.type == "undo":
        # Own most recent eligible operation still in history (compacted ops cannot be undone).
        target = undo_target(db, board, actor.id)
        if target is None:
            raise Conflict("nothing_to_undo", "You have nothing to undo on this board.")
        object_id = target.object_id
        payload = {"target_revision": target.revision, "target_type": target.op_type}
        if target.op_type == "move":
            payload.update(dx=target.payload["dx"], dy=target.payload["dy"])
    else:
        raise Invalid("invalid_board_op", "Unknown operation type.")
    board.revision += 1
    op = BoardOp(
        workspace_id=workspace_id,
        epoch=board.epoch,
        revision=board.revision,
        op_id=body.op_id,
        actor_id=actor.id,
        op_type=body.type,
        object_id=object_id,
        payload=payload,
        payload_hash=intent_hash,
    )
    db.add(op)
    # Logical charge (DL-07) commits atomically with the operation.
    after = with_op(objects, op)
    if board.charges_epoch == board.epoch:
        charge_board_object(db, workspace_id, object_id, after.get(object_id))
    else:
        recharge_board(db, board, after)  # first write to a historical board completes its ledger
    base_revision = board.base_revision
    db.commit()
    state_cache.committed(workspace_id, base_revision, op)
    committed = op_json(op)
    request.app.state.hub.publish(
        workspace_id, {"type": "board.op", "workspace_id": str(workspace_id), "op": committed}
    )
    return {"committed": committed, "duplicate": False}


@router.post("/workspaces/{workspace_id}/board/restore")
def restore(
    workspace_id: uuid.UUID,
    body: RestoreBody,
    request: Request,
    actor: Actor = Depends(current_actor),
    db: Session = Depends(get_db),
):
    """Start a new epoch holding the board as it was at ``revision`` (0 clears it). Stewards only."""
    policy.require_moderate(db, actor.user, workspace_id)
    policy.require_write(db, actor.user, workspace_id)
    board = _ensure_board(db, workspace_id)
    if body.revision > board.revision:
        raise Invalid("invalid_revision", "That revision does not exist yet.")
    objects = state_at(db, board, body.revision) if body.revision else {}
    old_epoch = board.epoch
    board.epoch += 1
    board.base_revision = board.revision
    restored: dict[str, dict] = {}
    for object_id, obj in objects.items():
        if not obj["alive"]:
            continue
        data = dict(obj["data"])
        if obj["kind"] == "stroke":
            data["points"] = [[p[0] + obj["dx"], p[1] + obj["dy"]] for p in data["points"]]
        else:
            data["x"], data["y"] = data["x"] + obj["dx"], data["y"] + obj["dy"]
        board.revision += 1
        payload = {"kind": obj["kind"], "data": data, "author": obj["author"]}
        restored[object_id] = {**payload, "alive": True}
        db.add(
            BoardOp(
                workspace_id=workspace_id,
                epoch=board.epoch,
                revision=board.revision,
                op_id=f"restore-{board.epoch}-{object_id}"[:64],
                actor_id=actor.id,
                op_type="add",
                object_id=object_id,
                payload=payload,
                payload_hash=_hash(payload),
            )
        )
    audit.record(
        db,
        actor=actor.user,
        action="board.restore",
        scope_type="workspace",
        scope_id=workspace_id,
        reason=body.reason,
        from_epoch=old_epoch,
        to_revision=body.revision,
    )
    recharge_board(db, board, restored)
    db.commit()
    request.app.state.hub.publish(
        workspace_id, {"type": "board.epoch", "workspace_id": str(workspace_id), "epoch": board.epoch}
    )
    return {"epoch": board.epoch, "revision": board.revision}


# ---- rendering and snapshot publishing -------------------------------------


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


def _render(db: Session, request: Request, workspace_id: uuid.UUID, revision: int, region: Region) -> bytes:
    board = db.get(Board, workspace_id)
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
    w: float = Query(gt=0),
    h: float = Query(gt=0),
    actor: Actor = Depends(current_actor),
    db: Session = Depends(get_db),
):
    """PNG of a region at a committed revision, for the publish preview."""
    policy.require_read(db, actor.user, workspace_id)
    png = _render(db, request, workspace_id, revision, Region(x=x, y=y, w=w, h=h))
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
            if access is not None and access.can_write:
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
                "can_write": policy.resolve(db, actor.user, w.id).can_write,
            }
            for w in dests
        ]
    }


@router.post("/workspaces/{workspace_id}/board/snapshots", status_code=201)
def publish_snapshot(
    workspace_id: uuid.UUID,
    body: SnapshotBody,
    request: Request,
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
    existing = db.scalar(select(Post).where(Post.author_id == actor.id, Post.client_id == body.client_id))
    if existing is not None:
        if (
            existing.source_workspace_id != workspace_id
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
    dest = policy.require_write(db, actor.user, body.destination_id).workspace
    if dest.id not in (source.id, body.confirm_audience):
        raise Invalid(
            "confirmation_required", f"Confirm that everyone who can read {dest.name} will see this snapshot."
        )
    png = _render(db, request, workspace_id, body.revision, body.region)
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
