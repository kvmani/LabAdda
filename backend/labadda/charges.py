"""Versioned canonical logical charges for text and board content (DL-07, T17).

Methods (stable identifiers; a new rule needs a new identifier, never a silent change):

* ``utf8-text-v1``: UTF-8 octets of user-authored text exactly as committed: post/reply
  body, chat body, note title plus body. No normalization, trimming or per-row overhead.
  Maintained by database triggers (migration 0014).
* ``board-object-json-v1``: UTF-8 octets of ``{"data":…,"kind":…}`` serialized as compact
  JSON with sorted keys and non-ASCII characters kept literal, for each live board object
  in the current epoch. Move offsets, authorship and history are not part of the charge;
  board history/snapshots are system overhead measured separately.

Charges are logical attribution to the stable contributor and the workspace. They are not
physical disk usage, grant no access and do not change admission (DL-07, DL-08).
"""

from __future__ import annotations

import json
import uuid

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from .models import Board, ContentCharge

TEXT_METHOD = "utf8-text-v1"
BOARD_METHOD = "board-object-json-v1"
TEXT_TYPES = ("post", "chat", "note")


def board_object_bytes(kind: str, data: dict) -> int:
    canonical = json.dumps(
        {"kind": kind, "data": data}, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )
    return len(canonical.encode("utf-8"))


def board_key(workspace_id: uuid.UUID, object_id: str) -> str:
    return f"{workspace_id}:{object_id}"


def expected_board_rows(workspace_id: uuid.UUID, objects: dict[str, dict]) -> dict[str, tuple]:
    """Ledger rows (key -> (user_id, bytes)) implied by a folded board state."""
    return {
        board_key(workspace_id, oid): (uuid.UUID(obj["author"]), board_object_bytes(obj["kind"], obj["data"]))
        for oid, obj in objects.items()
        if obj["alive"]
    }


def charge_board_object(db: Session, workspace_id: uuid.UUID, object_id: str, obj: dict | None) -> None:
    """Upsert one object's charge, or remove it when the object is not alive."""
    key = board_key(workspace_id, object_id)
    if obj is None or not obj["alive"]:
        db.execute(
            delete(ContentCharge).where(
                ContentCharge.item_type == "board_object", ContentCharge.item_key == key
            )
        )
        return
    values = {
        "item_type": "board_object",
        "item_key": key,
        "user_id": uuid.UUID(obj["author"]),
        "workspace_id": workspace_id,
        "method": BOARD_METHOD,
        "state": "live",
        "bytes": board_object_bytes(obj["kind"], obj["data"]),
        "updated_at": func.now(),
    }
    stmt = insert(ContentCharge).values(**values)
    db.execute(
        stmt.on_conflict_do_update(
            index_elements=["item_type", "item_key"],
            set_={k: stmt.excluded[k] for k in values if k not in ("item_type", "item_key")},
        )
    )


def recharge_board(db: Session, board: Board, objects: dict[str, dict]) -> None:
    """Replace a board's charges with those implied by ``objects`` and mark its epoch complete.

    Caller holds the board row lock, so no other writer interleaves.
    """
    db.execute(
        delete(ContentCharge).where(
            ContentCharge.item_type == "board_object", ContentCharge.workspace_id == board.workspace_id
        )
    )
    rows = [
        {
            "item_type": "board_object",
            "item_key": key,
            "user_id": user_id,
            "workspace_id": board.workspace_id,
            "method": BOARD_METHOD,
            "state": "live",
            "bytes": size,
        }
        for key, (user_id, size) in expected_board_rows(board.workspace_id, objects).items()
    ]
    if rows:
        db.execute(insert(ContentCharge).values(rows))
    board.charges_epoch = board.epoch


def summary(db: Session, user_id: uuid.UUID | None = None) -> dict:
    """Charge totals per type and state, plus board coverage. Metadata only."""
    query = select(
        ContentCharge.item_type,
        ContentCharge.state,
        func.count(),
        func.coalesce(func.sum(ContentCharge.bytes), 0),
    )
    if user_id is not None:
        query = query.where(ContentCharge.user_id == user_id)
    by_type = {
        t: {"live_bytes": 0, "live_items": 0, "removed_bytes": 0, "removed_items": 0}
        for t in (*TEXT_TYPES, "board_object")
    }
    for item_type, state, count, total in db.execute(
        query.group_by(ContentCharge.item_type, ContentCharge.state)
    ):
        by_type[item_type][f"{state}_bytes"] = int(total)
        by_type[item_type][f"{state}_items"] = count
    incomplete = db.scalar(
        select(func.count())
        .select_from(Board)
        .where(Board.revision > 0, Board.charges_epoch.is_distinct_from(Board.epoch))
    )
    return {
        "methods": {"text": TEXT_METHOD, "board": BOARD_METHOD},
        "by_type": by_type,
        "live_logical_bytes": sum(v["live_bytes"] for v in by_type.values()),
        "removed_logical_bytes": sum(v["removed_bytes"] for v in by_type.values()),
        # Unreconciled historical boards make board totals a lower bound, not a complete figure.
        "board_charges": "complete" if not incomplete else "incomplete",
        "unreconciled_boards": incomplete if user_id is None else None,
    }
