"""Current-administrator staff metadata reads; no inherited or content authority."""

import uuid
from collections.abc import Callable

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from .. import audit, people_export, people_profile
from .. import people_directory as directory
from ..config import Settings
from ..deps import Actor, current_actor, get_db, get_settings, require_console
from ..errors import ApiError
from ..people import StaffStatus

router = APIRouter(prefix="/admin/people", tags=["people"])
console_people = require_console("people")


def directory_filters(
    q: str = Query(default="", max_length=120),
    status: StaffStatus | None = None,
    unit_id: uuid.UUID | None = None,
    include_children: bool = True,
    role: directory.DirectoryRole | None = None,
    sort: directory.DirectorySort = "name",
    descending: bool = False,
) -> directory.DirectoryFilters:
    """Validate named filters once for directory and subsequent export reuse."""
    return directory.DirectoryFilters(q, status, unit_id, include_children, role, sort, descending)


def refresh_authority(request: Request, db: Session) -> Actor:
    """Recheck normal session, current identity and administration before delivery."""
    db.expire_all()
    return console_people(request, current_actor(request, db), db)


@router.get("")
def list_people(
    request: Request,
    filters: directory.DirectoryFilters = Depends(directory_filters),
    limit: int = Query(default=50, ge=1, le=100),
    cursor: str | None = Query(default=None, max_length=1024),
    actor: Actor = Depends(console_people),
    db: Session = Depends(get_db),
) -> dict:
    """Return bounded staff metadata and refuse stale authority, not an empty success."""
    return read_metadata(request, db, lambda: directory.directory_page(db, filters, limit, cursor))


def read_metadata(request: Request, db: Session, load: Callable[[], dict]) -> dict:
    """Bound metadata work and refresh authority after serialization."""
    try:
        db.execute(text("SET LOCAL statement_timeout = '2s'"))
        payload = load()
        refresh_authority(request, db)
        return payload
    except DBAPIError:
        db.rollback()
        raise ApiError(
            "people_unavailable", "Staff information is unavailable. Try again.", status=503
        ) from None


@router.get("/export.csv")
def export_people(
    request: Request,
    filters: directory.DirectoryFilters = Depends(directory_filters),
    actor: Actor = Depends(console_people),
    db: Session = Depends(get_db),
) -> Response:
    """Audit bounded report preparation, then recheck authority before delivery."""
    try:
        result = read_metadata(request, db, lambda: people_export.prepare_csv(db, filters))
        actor = refresh_authority(request, db)
        audit.record(db, actor=actor.user, action="people.export", scope_type="identity", rows=result["rows"])
        db.commit()
        refresh_authority(request, db)
        return Response(
            result["body"],
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": 'attachment; filename="people.csv"', "Cache-Control": "no-store"},
        )
    except DBAPIError:
        db.rollback()
        raise ApiError(
            "people_unavailable", "Staff information is unavailable. Try again.", status=503
        ) from None


@router.get("/{person_id}")
def get_person(
    person_id: uuid.UUID,
    request: Request,
    actor: Actor = Depends(console_people),
    db: Session = Depends(get_db),
) -> dict:
    """Read one current staff profile; administrators gain no private content access."""
    return read_metadata(request, db, lambda: people_profile.profile(db, person_id))


@router.get("/{person_id}/access")
def get_access(
    person_id: uuid.UUID,
    request: Request,
    limit: int = Query(default=50, ge=1, le=100),
    cursor: uuid.UUID | None = None,
    actor: Actor = Depends(console_people),
    db: Session = Depends(get_db),
) -> dict:
    """Read bounded direct/inherited grant metadata for this person only."""
    return read_metadata(request, db, lambda: people_profile.access_page(db, person_id, limit, cursor))


@router.get("/{person_id}/timeline")
def get_timeline(
    person_id: uuid.UUID,
    request: Request,
    limit: int = Query(default=50, ge=1, le=100),
    before: int | None = Query(default=None, ge=1),
    actor: Actor = Depends(console_people),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> dict:
    """Read staff-targeted audit history with date-only sign-in observations."""
    return read_metadata(
        request, db, lambda: people_profile.timeline_page(db, person_id, settings, limit, before)
    )
