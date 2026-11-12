"""GET /admin/setup-checklist: the live new-site checklist behind /admin/help/setup (HP-07)."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..config import Settings
from ..deps import Actor, get_db, get_settings, require_console
from ..security import utcnow
from ..setup_checklist import build_checklist

router = APIRouter(tags=["admin"])
console_help = require_console("help")


@router.get("/admin/setup-checklist")
def setup_checklist(
    _: Actor = Depends(console_help),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> dict:
    return build_checklist(db, settings, utcnow())
