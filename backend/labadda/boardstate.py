"""Board state: folding operations, history compaction and PNG rendering.

State is a dict ``object_id -> {kind, data, author, alive, rev, dx, dy}``.
Compaction folds old operations into a ``BoardSnapshot`` row and deletes
them, keeping the most recent revisions for undo, restore and replay.
"""

from __future__ import annotations

import copy
import io
import json
import logging
import threading
import time
import uuid
from collections.abc import Callable, Iterable

from PIL import Image, ImageDraw, ImageFont
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from .errors import Invalid
from .models import Board, BoardOp, BoardSnapshot

log = logging.getLogger("labadda.board")
MAX_RENDER_PX = 1600
MAX_REGION = 20_000
STICKY_W, STICKY_H = 180, 120


def apply_op(objects: dict[str, dict], op: BoardOp, by_rev: dict[int, BoardOp] | None = None) -> None:
    """Apply one committed operation to ``objects`` in place."""
    if by_rev is not None:
        by_rev[op.revision] = op
    obj = objects.get(op.object_id)
    if op.op_type == "add":
        objects[op.object_id] = {"kind": op.payload["kind"], "data": op.payload["data"],
                                 "author": op.payload.get("author", str(op.actor_id)), "alive": True,
                                 "rev": op.revision, "dx": 0.0, "dy": 0.0}
    elif obj is None:
        return
    elif op.op_type == "erase":
        obj["alive"], obj["rev"] = False, op.revision
    elif op.op_type == "move":
        obj["dx"] += op.payload["dx"]
        obj["dy"] += op.payload["dy"]
        obj["rev"] = op.revision
    elif op.op_type == "undo":
        # Undo payloads carry their effect so they still apply after the target is compacted.
        target_type = op.payload.get("target_type")
        delta = (op.payload.get("dx", 0.0), op.payload.get("dy", 0.0))
        if target_type is None:
            target = (by_rev or {}).get(op.payload["target_revision"])
            if target is None:
                return
            target_type = target.op_type
            if target_type == "move":
                delta = (target.payload["dx"], target.payload["dy"])
        if target_type == "add":
            obj["alive"] = False
        elif target_type == "erase":
            obj["alive"] = True
        elif target_type == "move":
            obj["dx"] -= delta[0]
            obj["dy"] -= delta[1]
        obj["rev"] = op.revision


def fold(ops: Iterable[BoardOp], base: dict | None = None, upto: int | None = None) -> dict[str, dict]:
    objects: dict[str, dict] = copy.deepcopy(base) if base else {}
    by_rev: dict[int, BoardOp] = {}
    for op in ops:
        if upto is not None and op.revision > upto:
            break
        apply_op(objects, op, by_rev)
    return objects


def _apply_copy(objects: dict[str, dict], op: BoardOp) -> None:
    """Apply ``op`` without mutating object dicts that other readers may still hold."""
    if op.object_id in objects:
        objects[op.object_id] = dict(objects[op.object_id])
    apply_op(objects, op)


def with_op(objects: dict[str, dict], op: BoardOp) -> dict[str, dict]:
    """A new state with ``op`` applied; ``objects`` and its object dicts are left untouched."""
    result = dict(objects)
    _apply_copy(result, op)
    return result


class StateCache:
    """Per-process cache of each board's latest state, so a write does not refold history.

    Entries are keyed by (epoch, revision). Compaction does not change state, so an entry stays
    valid across it and catches up incrementally as long as the operations after the cached
    revision are still retained (cached revision >= compacted base). Otherwise the state is
    rebuilt from the snapshot and operations.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._entries: dict[uuid.UUID, tuple[int, int, dict]] = {}

    def objects(self, db: Session, board: Board) -> dict[str, dict]:
        """Current state for a locked board row. Catches up incrementally when slightly behind."""
        with self._lock:
            entry = self._entries.get(board.workspace_id)
        if entry and entry[0] == board.epoch and board.base_revision <= entry[1] <= board.revision:
            objects = entry[2]
            if entry[1] < board.revision:
                objects = dict(objects)
                for op in epoch_ops(db, board.workspace_id, board.epoch, after=entry[1], upto=board.revision):
                    _apply_copy(objects, op)
        else:
            objects = state_at(db, board)
        self._store(board.workspace_id, board.epoch, board.revision, objects)
        return objects

    def committed(self, workspace_id: uuid.UUID, base_revision: int, op: BoardOp) -> None:
        """Advance the cached state after ``op`` has committed (ignored unless it is the next revision)."""
        with self._lock:
            entry = self._entries.get(workspace_id)
            if not entry or entry[0] != op.epoch or entry[1] != op.revision - 1:
                return  # the next read catches up from the database
            objects = dict(entry[2])
            _apply_copy(objects, op)
            self._entries[workspace_id] = (op.epoch, op.revision, objects)

    def _store(self, workspace_id, epoch, revision, objects) -> None:
        with self._lock:
            current = self._entries.get(workspace_id)
            # Never move an entry backwards within the same epoch.
            if current and current[0] == epoch and current[1] > revision:
                return
            self._entries[workspace_id] = (epoch, revision, objects)

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()


state_cache = StateCache()


def undo_target(db: Session, board: Board, actor_id) -> BoardOp | None:
    """The actor's most recent operation in retained history that is not already undone."""
    undone: set[int] = set()
    rows = db.scalars(select(BoardOp).where(BoardOp.workspace_id == board.workspace_id, BoardOp.epoch == board.epoch,
                                            BoardOp.revision > board.base_revision, BoardOp.actor_id == actor_id)
                      .order_by(BoardOp.revision.desc()))
    for op in rows:
        if op.op_type == "undo":
            undone.add(op.payload["target_revision"])
        elif op.revision not in undone and not op.op_id.startswith("restore-"):
            return op
    return None


def latest_snapshot(db: Session, workspace_id, epoch: int, upto: int | None = None) -> BoardSnapshot | None:
    stmt = select(BoardSnapshot).where(BoardSnapshot.workspace_id == workspace_id, BoardSnapshot.epoch == epoch)
    if upto is not None:
        stmt = stmt.where(BoardSnapshot.revision <= upto)
    return db.scalar(stmt.order_by(BoardSnapshot.revision.desc()).limit(1))


def epoch_ops(db: Session, workspace_id, epoch: int, after: int = 0, upto: int | None = None) -> list[BoardOp]:
    stmt = select(BoardOp).where(BoardOp.workspace_id == workspace_id, BoardOp.epoch == epoch,
                                 BoardOp.revision > after)
    if upto is not None:
        stmt = stmt.where(BoardOp.revision <= upto)
    return list(db.scalars(stmt.order_by(BoardOp.revision)))


def state_at(db: Session, board: Board, revision: int | None = None) -> dict[str, dict]:
    """Objects in the current epoch at ``revision`` (default: latest)."""
    target = board.revision if revision is None else revision
    snap = latest_snapshot(db, board.workspace_id, board.epoch, upto=target)
    if target < board.base_revision and (snap is None or snap.revision != target):
        raise Invalid("revision_compacted", "That revision is too old to rebuild. Choose a more recent one.")
    base_rev = snap.revision if snap else 0
    return fold(epoch_ops(db, board.workspace_id, board.epoch, after=base_rev, upto=target),
                base=snap.state if snap else None)


def compact(db: Session, board: Board, keep: int) -> int:
    """Fold operations older than the last ``keep`` revisions into a snapshot. Caller holds the board lock."""
    new_base = board.revision - keep
    if new_base <= board.base_revision:
        return 0
    state = state_at(db, board, new_base)
    db.add(BoardSnapshot(workspace_id=board.workspace_id, epoch=board.epoch, revision=new_base, state=state))
    removed = db.execute(delete(BoardOp).where(BoardOp.workspace_id == board.workspace_id,
                                               BoardOp.epoch == board.epoch, BoardOp.revision <= new_base)).rowcount
    board.base_revision = new_base
    return removed or 0


def compact_all(db: Session, threshold: int, keep: int) -> int:
    """Compact boards with more than ``threshold`` uncompacted revisions, keeping the last ``keep``.

    Two phases so drawing is not blocked: the expensive fold runs without any board lock, because
    operations at or below the new base (and this epoch's snapshots) are immutable once committed.
    The board row is then locked only to recheck that epoch and base are unchanged and to write the
    snapshot. A board restored or compacted in between is skipped and retried on a later tick.
    """
    candidates = db.execute(select(Board.workspace_id, Board.epoch, Board.revision, Board.base_revision)
                            .where(Board.revision - Board.base_revision > threshold)).all()
    db.commit()
    compacted = 0
    for workspace_id, epoch, revision, base in candidates:
        new_base = revision - keep
        if new_base <= base:
            continue
        started = time.perf_counter()
        observed = Board(workspace_id=workspace_id, epoch=epoch, revision=revision, base_revision=base)
        state = state_at(db, observed, new_base)  # no lock held: reads only immutable history
        db.commit()
        folded = time.perf_counter()
        board = db.scalar(select(Board).where(Board.workspace_id == workspace_id).with_for_update(skip_locked=True))
        if board is None or board.epoch != epoch or board.base_revision != base:
            db.rollback()
            continue
        db.add(BoardSnapshot(workspace_id=workspace_id, epoch=epoch, revision=new_base, state=state))
        removed = db.execute(delete(BoardOp).where(BoardOp.workspace_id == workspace_id, BoardOp.epoch == epoch,
                                                   BoardOp.revision <= new_base)).rowcount
        board.base_revision = new_base
        db.commit()
        compacted += 1
        # Operational timing only (no content): lock-held time is what can delay drawing.
        log.info(json.dumps({"event": "board.compacted", "operations_removed": removed,
                             "fold_ms": round((folded - started) * 1000, 1),
                             "locked_ms": round((time.perf_counter() - folded) * 1000, 1)}))
    return compacted


def bounds(o: dict) -> tuple[float, float, float, float]:
    d, dx, dy = o["data"], o["dx"], o["dy"]
    if o["kind"] == "stroke":
        xs = [p[0] + dx for p in d["points"]]
        ys = [p[1] + dy for p in d["points"]]
        pad = d.get("width", 3) / 2
        return min(xs) - pad, min(ys) - pad, max(xs) + pad, max(ys) + pad
    if o["kind"] == "image":
        return d["x"] + dx, d["y"] + dy, d["x"] + dx + d["w"], d["y"] + dy + d["h"]
    if o["kind"] == "sticky":
        return d["x"] + dx, d["y"] + dy, d["x"] + dx + STICKY_W, d["y"] + dy + STICKY_H
    return d["x"] + dx, d["y"] + dy, d["x"] + dx + max(40, len(d["text"]) * 9), d["y"] + dy + 24


def _hex(color: str) -> tuple[int, int, int]:
    return tuple(int(color[i:i + 2], 16) for i in (1, 3, 5))  # type: ignore[return-value]


def render_png(objects: dict[str, dict], region: tuple[float, float, float, float],
               load_image: Callable[[uuid.UUID], Image.Image | None]) -> bytes:
    """Render live objects inside ``region`` (x, y, w, h in board units) to a fresh PNG."""
    x0, y0, w, h = region
    if not (1 <= w <= MAX_REGION and 1 <= h <= MAX_REGION):
        raise Invalid("invalid_region", "Select a region between 1 and 20000 units wide and high.")
    scale = min(1.0, MAX_RENDER_PX / max(w, h))
    img = Image.new("RGB", (max(1, round(w * scale)), max(1, round(h * scale))), "white")
    draw = ImageDraw.Draw(img)
    font = ImageFont.load_default(size=max(8, round(16 * scale)))

    def pt(px: float, py: float) -> tuple[float, float]:
        return (px - x0) * scale, (py - y0) * scale

    def visible(o: dict) -> bool:
        a, b, c, d = bounds(o)
        return c >= x0 and a <= x0 + w and d >= y0 and b <= y0 + h

    for o in sorted((o for o in objects.values() if o["alive"]), key=lambda o: o["rev"]):
        if not visible(o):
            continue
        d, dx, dy = o["data"], o["dx"], o["dy"]
        if o["kind"] == "stroke":
            pts = [pt(p[0] + dx, p[1] + dy) for p in d["points"]]
            width = max(1, round(d["width"] * scale))
            if len(pts) == 1:
                r = width / 2
                draw.ellipse([pts[0][0] - r, pts[0][1] - r, pts[0][0] + r, pts[0][1] + r], fill=_hex(d["color"]))
            else:
                draw.line(pts, fill=_hex(d["color"]), width=width, joint="curve")
        elif o["kind"] == "image":
            src = load_image(uuid.UUID(d["asset_id"]))
            if src is None:
                continue
            a = pt(d["x"] + dx, d["y"] + dy)
            size = (max(1, round(d["w"] * scale)), max(1, round(d["h"] * scale)))
            tile = src.convert("RGBA").resize(size)
            img.paste(tile, (round(a[0]), round(a[1])), tile)
        else:
            a = pt(d["x"] + dx, d["y"] + dy)
            if o["kind"] == "sticky":
                b = pt(d["x"] + dx + STICKY_W, d["y"] + dy + STICKY_H)
                draw.rectangle([a, b], fill=_hex(d["color"]), outline=(200, 200, 200))
                draw.multiline_text((a[0] + 10 * scale, a[1] + 6 * scale), d["text"], fill=(31, 41, 51), font=font)
            else:
                draw.multiline_text((a[0], a[1] + 4 * scale), d["text"], fill=_hex(d["color"]), font=font)
    out = io.BytesIO()
    img.save(out, format="PNG")
    return out.getvalue()
