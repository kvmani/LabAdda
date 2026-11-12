"""Administrator-only list and cancellation of scheduled staff changes (PO-06)."""

import uuid

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from ..changes import scheduled, service
from ..changes.requests import _ordinary_reason
from ..deps import Actor, get_db, get_settings, require_console
from ..errors import ApiError
from .people import read_metadata

router = APIRouter(prefix="/admin/changes/scheduled", tags=["people changes"])
console_people = require_console("people", unit_admin=True)


@router.get("")
def list_scheduled(
    request: Request,
    person_id: uuid.UUID | None = None,
    actor: Actor = Depends(console_people),
    db: Session = Depends(get_db),
) -> dict:
    """Changes waiting for their day or for review: names, dates and the sentences reviewed."""
    return read_metadata(
        request,
        db,
        actor,
        lambda scope: scheduled.listing(db, person_id, None if scope is None else actor.user),
    )


@router.delete("/{change_id}")
def cancel_scheduled(
    change_id: uuid.UUID,
    request: Request,
    reason: str = Query(min_length=3, max_length=500),
    actor: Actor = Depends(console_people),
    db: Session = Depends(get_db),
) -> dict:
    """Withdraw a change before it runs, with an audited reason."""
    try:
        user = service.authorize(db, actor, get_settings(request))
        return scheduled.cancel(db, user, change_id, _ordinary_reason(reason.strip()))
    except DBAPIError:
        db.rollback()
        raise ApiError(
            "changes_unavailable", "The change could not be cancelled. Try again.", status=503
        ) from None
    except Exception:
        db.rollback()
        raise
