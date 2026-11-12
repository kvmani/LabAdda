"""Activity page figures with small-group protection, and their audited CSV export (AD-08)."""

from __future__ import annotations

from collections.abc import Callable

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from .. import analytics, audit
from ..analytics import export
from ..config import Settings
from ..deps import Actor, current_actor, get_db, get_settings, require_console
from ..errors import ApiError
from ..security import utcnow

router = APIRouter(prefix="/admin/analytics", tags=["analytics"])
console_activity = require_console("activity")

UNAVAILABLE = ("analytics_unavailable", "Usage figures are unavailable. Try again.")
BUILDERS: dict[str, Callable[..., dict]] = {
    "summary": analytics.build_summary,
    "units": analytics.build_units,
}


def refresh_authority(request: Request, db: Session) -> Actor:
    """Recheck the signed-in reader just before figures are returned."""
    db.expire_all()
    return console_activity(request, current_actor(request, db), db)


def _figures(db: Session, settings: Settings, kind: str, period: str) -> dict:
    def build() -> dict:
        db.execute(text("SET LOCAL statement_timeout = '2s'"))
        return BUILDERS[kind](db, settings, period, now=utcnow())

    return analytics.CACHE.get((kind, period, settings.timezone), build)


def _read(request: Request, db: Session, settings: Settings, kind: str, period: str) -> dict:
    try:
        payload = _figures(db, settings, kind, period)
        refresh_authority(request, db)
        return payload
    except DBAPIError:
        db.rollback()
        raise ApiError(*UNAVAILABLE, status=503) from None


@router.get("/summary")
def summary(
    request: Request,
    period: analytics.Period = Query(default="30d"),
    actor: Actor = Depends(console_activity),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> dict:
    return _read(request, db, settings, "summary", period)


@router.get("/units")
def units(
    request: Request,
    period: analytics.Period = Query(default="30d"),
    actor: Actor = Depends(console_activity),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> dict:
    return _read(request, db, settings, "units", period)


@router.get("/export.csv")
def export_csv(
    request: Request,
    period: analytics.Period = Query(default="30d"),
    actor: Actor = Depends(console_activity),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> Response:
    """The page's own protected figures, audited before delivery."""
    try:
        found = export.rows(
            _figures(db, settings, "summary", period), _figures(db, settings, "units", period)
        )
        actor = refresh_authority(request, db)
        audit.record(
            db,
            actor=actor.user,
            action="analytics.export",
            scope_type="site",
            period=analytics.PERIOD_WORDS[period],
            rows=len(found),
        )
        db.commit()
        refresh_authority(request, db)
    except DBAPIError:
        db.rollback()
        raise ApiError(*UNAVAILABLE, status=503) from None
    return Response(
        export.to_csv(found),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="activity-{period}.csv"',
            "Cache-Control": "no-store",
        },
    )
