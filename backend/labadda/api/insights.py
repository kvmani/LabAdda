"""Console Insights: feature momentum and request performance; counts and timings only."""

from __future__ import annotations

from collections.abc import Callable

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from .. import analytics, insights
from ..config import Settings
from ..deps import Actor, current_actor, get_db, get_settings, require_console
from ..errors import ApiError, Invalid
from ..security import utcnow

router = APIRouter(prefix="/admin/insights", tags=["insights"])
console_insights = require_console("insights")

UNAVAILABLE = ("insights_unavailable", "Insights are unavailable. Try again.")


def _read(request: Request, db: Session, key: tuple, build: Callable[[], dict]) -> dict:
    def timed() -> dict:
        db.execute(text("SET LOCAL statement_timeout = '3s'"))
        return build()

    try:
        payload = analytics.CACHE.get(key, timed)
        # Recheck the reader just before returning: access may have changed while reading.
        db.expire_all()
        console_insights(request, current_actor(request, db), db)
        return payload
    except DBAPIError:
        db.rollback()
        raise ApiError(*UNAVAILABLE, status=503) from None


@router.get("/trends")
def trends(
    request: Request,
    weeks: int = Query(default=12),
    actor: Actor = Depends(console_insights),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> dict:
    """Weekly feature use over ``weeks`` whole weeks, with momentum and guidance."""
    if weeks not in insights.HORIZONS:
        raise Invalid("invalid_weeks", "Choose 8, 12, 26 or 52 weeks.")
    return _read(
        request,
        db,
        ("insights.trends", weeks, settings.timezone),
        lambda: insights.build_trends(db, settings, weeks, now=utcnow()),
    )


@router.get("/performance")
def performance(
    request: Request,
    span: insights.Span = Query(default="7d"),
    actor: Actor = Depends(console_insights),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> dict:
    """Response times, server errors and sign-in failures by feature area over ``span``."""
    return _read(
        request,
        db,
        ("insights.performance", span, settings.timezone),
        lambda: insights.build_performance(db, settings, span, now=utcnow()),
    )
