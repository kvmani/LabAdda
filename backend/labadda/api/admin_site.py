"""Console Backups and Settings pages and the site notice banner (A7)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from pydantic import AwareDatetime, BaseModel, Field
from sqlalchemy.orm import Session

from .. import banner as banners
from ..backup_report import backup_report
from ..config import Settings
from ..deps import PANEL_HEADER, Actor, current_actor, get_db, get_settings, require_console
from ..errors import Unauthenticated
from ..models import SiteBanner
from ..security import utcnow
from ..settings_report import settings_groups

router = APIRouter(tags=["admin"])
console_backups = require_console("backups")
console_settings = require_console("settings", admin_only=True)


class BannerBody(BaseModel):
    # Length is checked after whitespace is normalised, with the documented error code.
    message: str = Field(max_length=2000)
    level: banners.Level | None = None
    starts_at: AwareDatetime | None = None
    ends_at: AwareDatetime | None = None
    expected_revision: int = Field(ge=0)


@router.get("/admin/backups/status")
def backups_status(_: Actor = Depends(console_backups), settings: Settings = Depends(get_settings)):
    return backup_report(settings, utcnow())


@router.get("/admin/settings")
def read_settings(
    _: Actor = Depends(console_settings),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    return {
        "groups": settings_groups(settings),
        "banner": banners.banner_json(db.get(SiteBanner, 1)),
        "banner_max_length": banners.MAX_LENGTH,
    }


@router.put("/admin/settings/banner")
def put_banner(
    body: BannerBody,
    actor: Actor = Depends(console_settings),
    db: Session = Depends(get_db),
):
    row = banners.save_banner(
        db,
        actor.user,
        message=body.message,
        level=body.level,
        starts_at=body.starts_at,
        ends_at=body.ends_at,
        expected_revision=body.expected_revision,
    )
    return {"banner": banners.banner_json(row)}


@router.get("/site/banner")
def site_banner(request: Request, actor: Actor = Depends(current_actor), db: Session = Depends(get_db)):
    """The notice every signed-in person sees now; a board-only screen is not signed in as a person."""
    if request.headers.get(PANEL_HEADER) or actor.is_panel:
        raise Unauthenticated()
    row = banners.active_banner(db)
    shown = banners.banner_json(row)
    if shown is not None:
        del shown["revision"]
    return {"banner": shown}
