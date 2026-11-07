"""Persistent workspace whiteboard with sequenced, idempotent operations (S3, S4).

State is the fold of committed operations in the current epoch. Each
operation has a client-chosen ``op_id``; identity is (workspace, epoch,
actor, op_id). A retry with the same payload returns the committed result;
reuse with a different payload fails with 409. A restore starts a new epoch,
so pending operations against the old epoch are rejected.
"""

from __future__ import annotations

import hashlib
import json
import uuid

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from .. import audit, policy
from ..deps import Actor, current_actor, get_db
from ..errors import Conflict, Invalid
from ..models import Board, BoardOp
from ..serialize import iso

router = APIRouter(tags=["board"])
MAX_POINTS = 4000
MAX_TEXT = 1000
COLORS = {"#1f2933", "#c62828", "#1565c0", "#2e7d32", "#ef6c00", "#6a1b9a", "#fff59d", "#b3e5fc", "#c8e6c9",
          "#ffccbc"}


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


def _hash(payload: dict) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def op_json(op: BoardOp) -> dict:
    return {"revision": op.revision, "epoch": op.epoch, "op_id": op.op_id, "actor_id": str(op.actor_id),
            "type": op.op_type, "object_id": op.object_id, "payload": op.payload, "created_at": iso(op.created_at)}


def _ensure_board(db: Session, workspace_id: uuid.UUID) -> Board:
    db.execute(insert(Board).values(workspace_id=workspace_id, epoch=1, revision=0)
               .on_conflict_do_nothing(index_elements=["workspace_id"]))
    return db.scalar(select(Board).where(Board.workspace_id == workspace_id).with_for_update())


def fold(ops: list[BoardOp], upto: int | None = None) -> dict[str, dict]:
    """Fold operations into live objects: object_id -> {kind, data, author, alive, rev, dx, dy}."""
    objects: dict[str, dict] = {}
    by_rev: dict[int, BoardOp] = {}
    for op in ops:
        if upto is not None and op.revision > upto:
            break
        by_rev[op.revision] = op
        obj = objects.get(op.object_id)
        if op.op_type == "add":
            objects[op.object_id] = {"kind": op.payload["kind"], "data": op.payload["data"],
                                     "author": op.payload.get("author", str(op.actor_id)), "alive": True,
                                     "rev": op.revision, "dx": 0.0, "dy": 0.0}
        elif obj is None:
            continue
        elif op.op_type == "erase":
            obj["alive"], obj["rev"] = False, op.revision
        elif op.op_type == "move":
            obj["dx"] += op.payload["dx"]
            obj["dy"] += op.payload["dy"]
            obj["rev"] = op.revision
        elif op.op_type == "undo":
            target = by_rev.get(op.payload["target_revision"])
            if target is None:
                continue
            if target.op_type == "add":
                obj["alive"] = False
            elif target.op_type == "erase":
                obj["alive"] = True
            elif target.op_type == "move":
                obj["dx"] -= target.payload["dx"]
                obj["dy"] -= target.payload["dy"]
            obj["rev"] = op.revision
    return objects


def _epoch_ops(db: Session, workspace_id, epoch: int) -> list[BoardOp]:
    return list(db.scalars(select(BoardOp).where(BoardOp.workspace_id == workspace_id, BoardOp.epoch == epoch)
                           .order_by(BoardOp.revision)))


def _num(v, lo=-1e6, hi=1e6) -> float:
    if not isinstance(v, (int, float)) or isinstance(v, bool) or not lo <= v <= hi:
        raise Invalid("invalid_board_op", "Board coordinates are out of range.")
    return float(v)


def _validate_add(payload: dict) -> dict:
    kind = payload.get("kind")
    data = payload.get("data") or {}
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
        return {"kind": kind, "data": {"x": _num(data.get("x")), "y": _num(data.get("y")), "text": text,
                                       "color": color}}
    raise Invalid("invalid_board_op", "Unknown board object kind.")


@router.get("/workspaces/{workspace_id}/board")
def get_board(workspace_id: uuid.UUID, epoch: int | None = None, after: int | None = None,
              actor: Actor = Depends(current_actor), db: Session = Depends(get_db)):
    access = policy.require_read(db, actor.user, workspace_id)
    board = db.get(Board, workspace_id)
    current_epoch, revision = (board.epoch, board.revision) if board else (1, 0)
    stmt = select(BoardOp).where(BoardOp.workspace_id == workspace_id, BoardOp.epoch == current_epoch)
    replay = epoch == current_epoch and after is not None
    if replay:
        stmt = stmt.where(BoardOp.revision > after)
    ops = db.scalars(stmt.order_by(BoardOp.revision)).all()
    return {"epoch": current_epoch, "revision": revision, "reset": not replay,
            "ops": [op_json(o) for o in ops], "can_write": access.can_write, "can_moderate": access.can_moderate}


@router.post("/workspaces/{workspace_id}/board/ops")
def submit_op(workspace_id: uuid.UUID, body: OpBody, request: Request, actor: Actor = Depends(current_actor),
              db: Session = Depends(get_db)):
    policy.require_write(db, actor.user, workspace_id)
    board = _ensure_board(db, workspace_id)  # row lock serializes sequencing per board
    intent = {"type": body.type, "object_id": body.object_id, "payload": body.payload,
              "base_revision": body.base_revision}
    intent_hash = _hash(intent)
    existing = db.scalar(select(BoardOp).where(BoardOp.workspace_id == workspace_id, BoardOp.epoch == body.epoch,
                                               BoardOp.actor_id == actor.id, BoardOp.op_id == body.op_id))
    if existing is not None:
        db.rollback()
        if existing.payload_hash != intent_hash:
            raise Conflict("op_id_reused", "This operation ID was already used for a different change.")
        return {"committed": op_json(existing), "duplicate": True}
    if body.epoch != board.epoch:
        db.rollback()
        raise Conflict("stale_epoch", "The board was restored. Reload to continue.")
    ops = _epoch_ops(db, workspace_id, board.epoch)
    objects = fold(ops)
    if body.type == "add":
        object_id = body.object_id or ""
        if not object_id or object_id in objects:
            raise Conflict("object_exists", "That board object already exists.")
        payload = _validate_add(body.payload)
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
        undone = {o.payload["target_revision"] for o in ops if o.op_type == "undo"}
        target = next((o for o in reversed(ops) if o.actor_id == actor.id and o.op_type != "undo"
                       and o.revision not in undone and o.op_id[:8] != "restore-"), None)
        if target is None:
            raise Conflict("nothing_to_undo", "You have nothing to undo on this board.")
        object_id, payload = target.object_id, {"target_revision": target.revision}
    else:
        raise Invalid("invalid_board_op", "Unknown operation type.")
    board.revision += 1
    op = BoardOp(workspace_id=workspace_id, epoch=board.epoch, revision=board.revision, op_id=body.op_id,
                 actor_id=actor.id, op_type=body.type, object_id=object_id, payload=payload,
                 payload_hash=intent_hash)
    db.add(op)
    db.commit()
    committed = op_json(op)
    request.app.state.hub.publish(workspace_id, {"type": "board.op", "workspace_id": str(workspace_id),
                                                 "op": committed})
    return {"committed": committed, "duplicate": False}


@router.post("/workspaces/{workspace_id}/board/restore")
def restore(workspace_id: uuid.UUID, body: RestoreBody, request: Request, actor: Actor = Depends(current_actor),
            db: Session = Depends(get_db)):
    """Start a new epoch holding the board as it was at ``revision`` (0 clears it). Stewards only."""
    policy.require_moderate(db, actor.user, workspace_id)
    policy.require_write(db, actor.user, workspace_id)
    board = _ensure_board(db, workspace_id)
    if body.revision > board.revision:
        raise Invalid("invalid_revision", "That revision does not exist yet.")
    objects = fold(_epoch_ops(db, workspace_id, board.epoch), upto=body.revision)
    old_epoch = board.epoch
    board.epoch += 1
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
        db.add(BoardOp(workspace_id=workspace_id, epoch=board.epoch, revision=board.revision,
                       op_id=f"restore-{board.epoch}-{object_id}"[:64], actor_id=actor.id, op_type="add",
                       object_id=object_id, payload=payload, payload_hash=_hash(payload)))
    audit.record(db, actor=actor.user, action="board.restore", scope_type="workspace", scope_id=workspace_id,
                 reason=body.reason, from_epoch=old_epoch, to_revision=body.revision)
    db.commit()
    request.app.state.hub.publish(workspace_id, {"type": "board.epoch", "workspace_id": str(workspace_id),
                                                 "epoch": board.epoch})
    return {"epoch": board.epoch, "revision": board.revision}
