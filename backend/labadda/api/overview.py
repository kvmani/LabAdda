"""GET /admin/overview: the console landing page in one request (A6, AD-12)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from ..config import Settings
from ..deps import Actor, current_actor, get_db, get_settings, require_console
from ..errors import ApiError
from ..overview import build_overview
from ..security import utcnow
from .health import current_items

router = APIRouter(tags=["overview"])
console_overview = require_console("overview")

UNAVAILABLE = ("overview_unavailable", "The overview is unavailable. Try again.")


@router.get("/admin/overview")
def overview(
    request: Request,
    actor: Actor = Depends(console_overview),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> dict:
    items = current_items(request)
    try:
        db.execute(text("SET LOCAL statement_timeout = '2s'"))
        payload = build_overview(db, settings, items, now=utcnow())
        # Authority is rechecked after reading, just before the figures leave (AD-01).
        db.expire_all()
        console_overview(request, current_actor(request, db), db)
    except DBAPIError:
        db.rollback()
        raise ApiError(*UNAVAILABLE, status=503) from None
    return payload
