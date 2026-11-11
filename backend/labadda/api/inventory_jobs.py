"""Bounded read-only operational job history; no web execution or content access."""

import uuid
from typing import Literal

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import and_, func, or_, select, text
from sqlalchemy.orm import Session

from ..deps import PANEL_HEADER, Actor, current_actor, get_db, require_console
from ..errors import NotFound, Unauthenticated
from ..inventory_jobs import describe
from ..models import InventoryJob
from ..serialize import iso
from .capabilities import require_usage_reader

router = APIRouter(tags=["inventory-jobs"])
console_storage = require_console("storage")
JobState = Literal["queued", "running", "completed", "partial", "failed", "paused", "cancelled"]


def _normal(request):
    if request.headers.get(PANEL_HEADER) or request.query_params.get("panel") == "1":
        raise Unauthenticated("session_scope", "Use a normal session for operational jobs.")


def _recheck(request, db):
    db.expire_all()
    require_usage_reader(current_actor(request, db), db)


@router.get("/admin/inventory-jobs")
def jobs(
    request: Request,
    state: JobState | None = None,
    before: uuid.UUID | None = None,
    limit: int = Query(default=20, ge=1, le=25),
    actor: Actor = Depends(console_storage),
    db: Session = Depends(get_db),
):
    _normal(request)
    db.execute(text("set local statement_timeout = '2s'"))
    query = select(InventoryJob)
    if state:
        query = query.where(InventoryJob.state == state)
    if before:
        anchor = db.get(InventoryJob, before)
        if anchor is None:
            raise NotFound()
        query = query.where(
            or_(
                InventoryJob.created_at < anchor.created_at,
                and_(InventoryJob.created_at == anchor.created_at, InventoryJob.id < anchor.id),
            )
        )
    rows = db.scalars(
        query.order_by(InventoryJob.created_at.desc(), InventoryJob.id.desc()).limit(limit + 1)
    ).all()
    now = db.scalar(select(func.clock_timestamp()))
    result = {
        "jobs": [describe(db, row, now=now, include_attempts=False) for row in rows[:limit]],
        "next_cursor": str(rows[limit - 1].id) if len(rows) > limit else None,
        "observed_at": iso(now),
        "maximum_returned": limit,
        "enforcement_authority": False,
        "execution": "trusted_operator_cli",
        "history_included": False,
    }
    _recheck(request, db)
    return result


@router.get("/admin/inventory-jobs/{job_id}")
def job(
    request: Request,
    job_id: uuid.UUID,
    actor: Actor = Depends(console_storage),
    db: Session = Depends(get_db),
):
    _normal(request)
    db.execute(text("set local statement_timeout = '2s'"))
    row = db.get(InventoryJob, job_id)
    if row is None:
        raise NotFound()
    result = describe(db, row)
    _recheck(request, db)
    return result
