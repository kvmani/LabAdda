"""Owner-derived private board access, revision conflicts and retained history."""

import json
import uuid
from typing import Literal

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..deps import PANEL_HEADER, Actor, current_actor, get_db, get_settings
from ..errors import Conflict, Unauthenticated
from ..identity_locks import lock_identity
from ..models import PersonalBoardRevision

router = APIRouter(prefix="/me/whiteboard", tags=["personal whiteboard"])


class BoardObject(BaseModel):
    """Finite bounded coordinates and safe text; no arbitrary SVG or HTML."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    id: uuid.UUID
    kind: Literal["stroke", "sticky"]
    color: Literal["teal", "blue", "orange", "yellow", "mint", "pink", "purple"]
    x: float = Field(default=0, ge=0, le=1000)
    y: float = Field(default=0, ge=0, le=600)
    text: str = Field(default="", max_length=1000)
    points: list[tuple[float, float]] = Field(default_factory=list, max_length=2000)

    @model_validator(mode="after")
    def bounded_points(self):
        if any(not (0 <= x <= 1000 and 0 <= y <= 600) for x, y in self.points):
            raise ValueError("Drawing points must stay on the board")
        return self


class BoardSave(BaseModel):
    """A bounded complete document with its expected revision."""

    model_config = ConfigDict(extra="forbid")
    revision: int = Field(ge=0, strict=True)
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


def _latest(db: Session, owner_id):
    return db.scalar(
        select(PersonalBoardRevision)
        .where(PersonalBoardRevision.owner_id == owner_id)
        .order_by(PersonalBoardRevision.revision.desc())
        .limit(1)
    )


def _document(row):
    return {"revision": row.revision, "objects": row.objects} if row else {"revision": 0, "objects": []}


@router.get("")
def read_board(request: Request, actor: Actor = Depends(current_actor), db: Session = Depends(get_db)):
    owner = _owner(request, actor, db)
    return _document(_latest(db, owner.id))


@router.put("")
def save_board(
    body: BoardSave, request: Request, actor: Actor = Depends(current_actor), db: Session = Depends(get_db)
):
    owner = _owner(request, actor, db)
    latest = _latest(db, owner.id)
    revision = latest.revision if latest else 0
    objects = [item.model_dump(mode="json") for item in body.objects]
    if body.revision != revision:
        if latest and body.revision == revision - 1 and latest.objects == objects:
            return _document(latest)
        raise Conflict(
            "stale_revision", "Your board changed in another tab. Keep your draft or load saved work."
        )
    row = PersonalBoardRevision(owner_id=owner.id, revision=revision + 1, objects=objects)
    db.add(row)
    db.commit()
    return _document(row)
