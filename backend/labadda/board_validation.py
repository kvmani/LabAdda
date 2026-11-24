"""Validation of whiteboard operations before they are committed (S3).

The server is the authority on what a board may hold: sizes, colours, shapes, text length and
image placement are checked here for every added or updated object.
"""

from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from . import metrics
from .board_fonts import validate_style
from .deps import Actor
from .errors import Invalid
from .models import Asset, Workspace

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
    "#e1bee7",
    "#ffe082",
    "#00838f",
    "#d81b60",
    "#757575",
}
STICKY_SHAPES = {"rectangle", "circle", "hexagon", "diamond", "cloud", "star"}
STICKY_SIZES = {"small", "medium", "large"}


def _num(v, lo=-1e6, hi=1e6) -> float:
    if not isinstance(v, (int, float)) or isinstance(v, bool) or not lo <= v <= hi:
        raise Invalid("invalid_board_op", "Board coordinates are out of range.")
    return float(v)


def _validate_sticky_or_text(kind: str, data: dict, color: str) -> dict:
    text = data.get("text")
    if not isinstance(text, str) or not text.strip() or len(text) > MAX_TEXT:
        raise Invalid("invalid_board_op", "Text must be 1-1000 characters.")
    item_data = {"x": _num(data.get("x")), "y": _num(data.get("y")), "text": text, "color": color}
    if "font_family" in data or "font_size" in data:
        item_data.update(validate_style(data))
    if kind == "sticky":
        if "shape" in data:
            shape = data["shape"]
            if shape not in STICKY_SHAPES:
                raise Invalid("invalid_board_op", "Unsupported sticky shape.")
            item_data["shape"] = shape
        if "size" in data:
            size = data["size"]
            if size not in STICKY_SIZES:
                raise Invalid("invalid_board_op", "Unsupported sticky size.")
            item_data["size"] = size
    return {"kind": kind, "data": item_data}


def validate_add(db: Session, actor: Actor, workspace_id: uuid.UUID, payload: dict) -> dict:
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
            metrics.count_attachments_on_commit(db, db.get(Workspace, workspace_id), [asset])
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
        return _validate_sticky_or_text(kind, data, color)
    raise Invalid("invalid_board_op", "Unknown board object kind.")
