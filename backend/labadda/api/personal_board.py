"""Owner-derived private board access, revision conflicts and retained history."""

import json
import re
import uuid
from typing import Literal

import sqlalchemy as sa
from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..deps import PANEL_HEADER, Actor, current_actor, get_db, get_settings
from ..errors import Conflict, Invalid, Unauthenticated
from ..identity_locks import lock_identity
from ..models import PersonalBoardRevision
from ..system_settings import get_max_whiteboards

router = APIRouter(prefix="/me/whiteboard", tags=["personal whiteboard"])


class PersonalTitlePatch(BaseModel):
    title: str = Field(min_length=1, max_length=64)

    @model_validator(mode="after")
    def validate_title_length(self):
        t = self.title.strip()
        # Default WhiteBoard_N is allowed; custom short names must be at most 10 characters
        if re.match(r"^WhiteBoard_\d+$", t, re.IGNORECASE):
            return self
        if len(t) > 10:
            raise ValueError("Board title must be at most 10 characters (or default WhiteBoard_N).")
        return self


class BoardObject(BaseModel):
    """Finite bounded coordinates and safe text; no arbitrary SVG or HTML."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    id: uuid.UUID
    kind: Literal["stroke", "sticky", "text", "image"]
    color: str = Field(default="#1f2933", min_length=1, max_length=32)
    shape: Literal["rectangle", "circle", "hexagon", "diamond", "cloud", "star"] = "rectangle"
    size: Literal["small", "medium", "large"] = "medium"
    x: float = Field(default=0, ge=0, le=1000)
    y: float = Field(default=0, ge=0, le=600)
    w: float = Field(default=0, ge=0, le=1000)
    h: float = Field(default=0, ge=0, le=600)
    text: str = Field(default="", max_length=1000)
    points: list[tuple[float, float]] = Field(default_factory=list, max_length=2000)
    width: float = Field(default=3, ge=1, le=50)
    asset_id: str | None = None
    author: str | None = None
    created_at: str | None = None

    @model_validator(mode="after")
    def bounded_points(self):
        if any(not (0 <= x <= 1000 and 0 <= y <= 600) for x, y in self.points):
            raise ValueError("Drawing points must stay on the board")
        return self


class BoardSave(BaseModel):
    """A bounded complete document with its expected revision."""

    model_config = ConfigDict(extra="forbid")
    revision: int = Field(ge=0, strict=True)
    board_index: int = Field(default=0, ge=0, le=50)
    objects: list[BoardObject] = Field(max_length=500)

    @model_validator(mode="after")
    def bounded_document(self):
        if len({item.id for item in self.objects}) != len(self.objects):
            raise ValueError("Object identifiers must be unique")
        if sum(len(item.points) for item in self.objects) > 20_000:
            raise ValueError("Too many drawing points")
        if len(json.dumps(self.model_dump(mode="json")).encode()) > 250_000:
            raise ValueError("Board is too large")
        return self


def _owner(request: Request, actor: Actor, db: Session):
    if request.headers.get(PANEL_HEADER) or request.query_params.get("panel") == "1":
        raise Unauthenticated()
    return lock_identity(db, actor, get_settings(request))


def _latest(db: Session, owner_id, board_index: int = 0):
    return db.scalar(
        select(PersonalBoardRevision)
        .where(
            PersonalBoardRevision.owner_id == owner_id,
            PersonalBoardRevision.board_index == board_index,
        )
        .order_by(PersonalBoardRevision.revision.desc())
        .limit(1)
    )


def _document(row, board_index: int = 0, explicit: bool = False):
    doc = {"revision": row.revision, "objects": row.objects} if row else {"revision": 0, "objects": []}
    if explicit or board_index > 0:
        doc["board_index"] = getattr(row, "board_index", board_index)
        doc["title"] = getattr(row, "title", f"WhiteBoard_{board_index + 1}")
    return doc


@router.get("")
def read_board(
    request: Request,
    board_index: int = Query(default=0, ge=0, le=50),
    actor: Actor = Depends(current_actor),
    db: Session = Depends(get_db),
):
    owner = _owner(request, actor, db)
    settings = get_settings(request)
    max_boards = get_max_whiteboards(db, settings)
    if board_index < 0 or board_index >= max_boards:
        raise Invalid("invalid_board_index", f"Board index must be between 0 and {max_boards - 1}.")
    explicit = "board_index" in request.query_params
    return _document(_latest(db, owner.id, board_index), board_index, explicit)


@router.get("/tabs")
def list_personal_boards(
    request: Request,
    actor: Actor = Depends(current_actor),
    db: Session = Depends(get_db),
):
    owner = _owner(request, actor, db)
    settings = get_settings(request)
    max_boards = get_max_whiteboards(db, settings)
    sub = (
        select(
            PersonalBoardRevision.board_index,
            sa.func.max(PersonalBoardRevision.revision).label("max_rev"),
        )
        .where(PersonalBoardRevision.owner_id == owner.id)
        .group_by(PersonalBoardRevision.board_index)
        .subquery()
    )
    rows = db.scalars(
        select(PersonalBoardRevision)
        .join(
            sub,
            sa.and_(
                PersonalBoardRevision.owner_id == owner.id,
                PersonalBoardRevision.board_index == sub.c.board_index,
                PersonalBoardRevision.revision == sub.c.max_rev,
            ),
        )
        .order_by(PersonalBoardRevision.board_index)
    ).all()
    by_idx = {r.board_index: r for r in rows}
    boards = []
    # Ensure at least board 0 exists
    if 0 not in by_idx:
        boards.append({"board_index": 0, "title": "WhiteBoard_1", "revision": 0})
    for r in rows:
        if r.board_index < max_boards:
            boards.append({"board_index": r.board_index, "title": r.title, "revision": r.revision})
    return {"boards": boards, "max_whiteboards": max_boards}


@router.patch("/{board_index}/title")
def update_personal_title(
    board_index: int,
    body: PersonalTitlePatch,
    request: Request,
    actor: Actor = Depends(current_actor),
    db: Session = Depends(get_db),
):
    owner = _owner(request, actor, db)
    settings = get_settings(request)
    max_boards = get_max_whiteboards(db, settings)
    if board_index < 0 or board_index >= max_boards:
        raise Invalid("invalid_board_index", f"Board index must be between 0 and {max_boards - 1}.")
    clean_title = body.title.strip() or f"WhiteBoard_{board_index + 1}"
    latest = _latest(db, owner.id, board_index)
    if latest:
        latest.title = clean_title
        db.commit()
        return {"board_index": board_index, "title": latest.title}
    row = PersonalBoardRevision(
        owner_id=owner.id,
        board_index=board_index,
        revision=0,
        title=clean_title,
        objects=[],
    )
    db.add(row)
    db.commit()
    return {"board_index": board_index, "title": row.title}


@router.put("")
def save_board(
    body: BoardSave,
    request: Request,
    board_index: int = Query(default=0, ge=0, le=50),
    actor: Actor = Depends(current_actor),
    db: Session = Depends(get_db),
):
    owner = _owner(request, actor, db)
    idx = body.board_index if body.board_index is not None else board_index
    settings = get_settings(request)
    max_boards = get_max_whiteboards(db, settings)
    if idx >= max_boards:
        raise Invalid("max_whiteboards_exceeded", f"Only {max_boards} whiteboards are allowed.")
    latest = _latest(db, owner.id, idx)
    revision = latest.revision if latest else 0
    title = latest.title if latest else f"WhiteBoard_{idx + 1}"
    objects = [item.model_dump(mode="json") for item in body.objects]
    explicit = "board_index" in request.query_params or "board_index" in body.model_fields_set
    if body.revision != revision:
        if latest and body.revision == revision - 1 and latest.objects == objects:
            return _document(latest, idx, explicit)
        raise Conflict(
            "stale_revision", "Your board changed in another tab. Keep your draft or load saved work."
        )
    row = PersonalBoardRevision(
        owner_id=owner.id,
        board_index=idx,
        revision=revision + 1,
        title=title,
        objects=objects,
    )
    db.add(row)
    db.commit()
    return _document(row, idx, explicit)
