"""Console Backups and Settings pages, site broadcasts (A7, AD-11) and the software version."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, Request
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from .. import broadcast as broadcasts
from .. import build_info
from ..backup_report import backup_report
from ..config import Settings
from ..deps import PANEL_HEADER, Actor, current_actor, get_db, get_settings, require_console
from ..errors import Invalid, Unauthenticated
from ..security import utcnow
from ..settings_report import settings_groups

router = APIRouter(tags=["admin"])
console_backups = require_console("backups")
console_settings = require_console("settings", admin_only=True)
console_broadcast = require_console("broadcast", admin_only=True)


class BroadcastBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    # Length is checked after whitespace is normalised, with the documented error code.
    message: str = Field(max_length=2000)
    level: broadcasts.Level
    starts_at: AwareDatetime | None = None
    ends_at: AwareDatetime | None = None
    active: bool = True


class BroadcastPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    message: str | None = Field(default=None, max_length=2000)
    level: broadcasts.Level | None = None
    starts_at: AwareDatetime | None = None
    ends_at: AwareDatetime | None = None
    active: bool | None = None
    expected_revision: int = Field(ge=1)


class MoveBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    direction: Literal["up", "down"]


@router.get("/admin/backups/status")
def backups_status(_: Actor = Depends(console_backups), settings: Settings = Depends(get_settings)):
    return backup_report(settings, utcnow())


@router.get("/admin/settings")
def read_settings(_: Actor = Depends(console_settings), settings: Settings = Depends(get_settings)):
    return {"groups": settings_groups(settings)}


@router.get("/admin/broadcasts")
def list_broadcasts(_: Actor = Depends(console_broadcast), db: Session = Depends(get_db)):
    return {"broadcasts": broadcasts.list_all(db), "max_length": broadcasts.MAX_LENGTH}


@router.post("/admin/broadcasts", status_code=201)
def add_broadcast(
    body: BroadcastBody, actor: Actor = Depends(console_broadcast), db: Session = Depends(get_db)
):
    row = broadcasts.add(
        db,
        actor.user,
        message=body.message,
        level=body.level,
        starts_at=body.starts_at,
        ends_at=body.ends_at,
        active=body.active,
    )
    return {"broadcast": broadcasts.broadcast_json(row, utcnow())}


@router.patch("/admin/broadcasts/{broadcast_id}")
def edit_broadcast(
    broadcast_id: int,
    body: BroadcastPatch,
    actor: Actor = Depends(console_broadcast),
    db: Session = Depends(get_db),
):
    changes = {name: getattr(body, name) for name in body.model_fields_set if name != "expected_revision"}
    if any(changes.get(name, "") is None for name in ("message", "level", "active")):
        raise Invalid("invalid_broadcast", "Message, level and shown cannot be empty.")
    row = broadcasts.edit(
        db, actor.user, broadcast_id, changes=changes, expected_revision=body.expected_revision
    )
    return {"broadcast": broadcasts.broadcast_json(row, utcnow())}


@router.post("/admin/broadcasts/{broadcast_id}/move")
def move_broadcast(
    broadcast_id: int,
    body: MoveBody,
    actor: Actor = Depends(console_broadcast),
    db: Session = Depends(get_db),
):
    broadcasts.move(db, actor.user, broadcast_id, body.direction)
    return {"broadcasts": broadcasts.list_all(db)}


@router.delete("/admin/broadcasts/{broadcast_id}")
def delete_broadcast(
    broadcast_id: int, actor: Actor = Depends(console_broadcast), db: Session = Depends(get_db)
):
    broadcasts.delete(db, actor.user, broadcast_id)
    return {"deleted": True}


@router.get("/site/version")
def site_version():
    """Public: which software this is (no user data), for support and the version footer."""
    return build_info.build_info()


@router.get("/site/broadcasts")
def site_broadcasts(request: Request, actor: Actor = Depends(current_actor), db: Session = Depends(get_db)):
    """The messages every signed-in person sees now; a board-only screen is not signed in as a person."""
    if request.headers.get(PANEL_HEADER) or actor.is_panel:
        raise Unauthenticated()
    return {"broadcasts": broadcasts.showing_now(db)}
