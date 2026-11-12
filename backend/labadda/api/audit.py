"""Administrator-only audit explorer: filtered pages and an audited, streamed CSV (AD-09)."""

import csv
import io
import uuid
from collections.abc import Callable, Iterator
from datetime import date, datetime

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from .. import audit, audit_catalog, audit_explorer
from ..audit_explorer import AuditFilters
from ..config import Settings
from ..deps import Actor, current_actor, get_db, get_settings, require_console
from ..errors import ApiError, Invalid
from ..people_export import safe_cell

router = APIRouter(prefix="/admin/audit", tags=["audit"])
console_audit = require_console("audit", admin_only=True)

EXPORT_LIMIT = 10_000
CHUNK = 500
COLUMNS = ("time", "who", "group", "what happened", "outcome", "reason", "action")
UNAVAILABLE = ("audit_unavailable", "The audit trail is unavailable. Try again.")


def audit_filters(
    start: date | None = None,
    end: date | None = None,
    actor_id: uuid.UUID | None = None,
    person_id: uuid.UUID | None = None,
    unit_id: uuid.UUID | None = None,
    *,
    group: str | None = Query(default=None, max_length=32),
    outcome: str | None = Query(default=None, max_length=16),
    q: str = Query(default="", max_length=120),
) -> AuditFilters:
    if group is not None and group not in audit_catalog.GROUPS:
        raise Invalid("invalid_group", "Choose one of the listed action groups.")
    if start and end and start > end:
        raise Invalid("invalid_range", "The end date must not be before the start date.")
    return AuditFilters(start, end, actor_id, person_id, unit_id, group, outcome or None, q)


def refresh_authority(request: Request, db: Session) -> Actor:
    """Recheck the signed-in administrator just before protected data is returned."""
    db.expire_all()
    return console_audit(request, current_actor(request, db), db)


def _bounded(request: Request, db: Session, load: Callable[[], dict]) -> dict:
    try:
        db.execute(text("SET LOCAL statement_timeout = '2s'"))
        payload = load()
        refresh_authority(request, db)
        return payload
    except DBAPIError:
        db.rollback()
        raise ApiError(*UNAVAILABLE, status=503) from None


@router.get("")
def list_audit(
    request: Request,
    *,
    filters: AuditFilters = Depends(audit_filters),
    limit: int = Query(default=100, ge=1, le=500),
    cursor: str | None = Query(default=None, max_length=1024),
    actor: Actor = Depends(console_audit),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> dict:
    return _bounded(
        request,
        db,
        lambda: audit_explorer.audit_page(db, filters, settings.timezone, limit, cursor),
    )


def _csv_line(values: list[str]) -> str:
    buffer = io.StringIO(newline="")
    csv.writer(buffer).writerow(values)
    return buffer.getvalue()


def _stream(request: Request, ids: list[int]) -> Iterator[str]:
    """Read in small chunks on a private session so a large export never holds one big result."""
    yield "﻿" + _csv_line(list(COLUMNS))
    with request.app.state.session_factory() as db:
        for offset in range(0, len(ids), CHUNK):
            events = audit_explorer.shape_events(
                db, audit_explorer.rows_by_id(db, ids[offset : offset + CHUNK])
            )
            for e in events:
                who = e["actor"]["display_name"] if e["actor"] else "Operator tooling"
                row = [
                    e["created_at"],
                    who,
                    e["group_label"],
                    e["sentence"],
                    e["outcome"],
                    e["reason"],
                    e["action"],
                ]
                yield _csv_line([safe_cell(str(value or "")) for value in row])
            db.expire_all()


@router.get("/export.csv")
def export_audit(
    request: Request,
    filters: AuditFilters = Depends(audit_filters),
    actor: Actor = Depends(console_audit),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> StreamingResponse:
    """Fix the row set, audit the export, recheck authority, then stream."""
    try:
        db.execute(text("SET LOCAL statement_timeout = '2s'"))
        ids = audit_explorer.export_ids(db, filters, settings.timezone, EXPORT_LIMIT)
        if len(ids) > EXPORT_LIMIT:
            raise Invalid(
                "export_limit", "Too many entries for one report. Narrow the filters and export again."
            )
        actor = refresh_authority(request, db)
        used = sorted(k for k, v in vars(filters).items() if v not in (None, ""))
        audit.record(
            db,
            actor=actor.user,
            action="audit.export",
            scope_type="site",
            rows=len(ids),
            filters=",".join(used),
        )
        db.commit()
        refresh_authority(request, db)
    except DBAPIError:
        db.rollback()
        raise ApiError(*UNAVAILABLE, status=503) from None
    stamp = datetime.now().strftime("%Y%m%d")
    return StreamingResponse(
        _stream(request, ids),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="audit-{stamp}.csv"',
            "Cache-Control": "no-store",
        },
    )
