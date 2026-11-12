"""Administrator-only reviewed staff changes; clients never supply executable plans."""

import uuid

from fastapi import APIRouter, Depends, Request
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from ..changes import activation, candidates, service
from ..changes.requests import ApplyRequest, PreviewRequest, ReissueRequest
from ..deps import Actor, get_db, get_settings, require_console
from ..errors import ApiError
from .people import read_metadata

router = APIRouter(prefix="/admin/changes", tags=["people changes"])
console_people = require_console("people")


@router.post("/preview")
def preview_change(
    body: PreviewRequest,
    request: Request,
    actor: Actor = Depends(console_people),
    db: Session = Depends(get_db),
) -> dict:
    """Return a bounded staff-only review without writing staff or audit rows."""
    try:
        return service.preview(db, actor, get_settings(request), body.request)
    except DBAPIError:
        db.rollback()
        raise ApiError(
            "changes_unavailable", "Staff changes are unavailable. Try again.", status=503
        ) from None


@router.post("/apply")
def apply_change(
    body: ApplyRequest,
    request: Request,
    actor: Actor = Depends(console_people),
    db: Session = Depends(get_db),
) -> dict:
    """Commit a current reviewed edit atomically, then refresh live identity delivery."""
    try:
        return service.apply(db, actor, get_settings(request), body, request.app.state.hub)
    except DBAPIError:
        db.rollback()
        raise ApiError(
            "changes_unavailable",
            "The change could not be confirmed. Reload the record before retrying.",
            status=503,
        ) from None


@router.post("/activation-code")
def reissue_activation(
    body: ReissueRequest,
    request: Request,
    actor: Actor = Depends(console_people),
    db: Session = Depends(get_db),
) -> dict:
    """Give an invited person a fresh one-time code; earlier unused codes stop working."""
    try:
        return activation.reissue(db, actor, get_settings(request), body.person_id, body.reason)
    except DBAPIError:
        db.rollback()
        raise ApiError(
            "changes_unavailable",
            "The new code could not be confirmed. Reload the record before retrying.",
            status=503,
        ) from None


@router.get("/candidates")
def change_candidates(
    workspace_id: uuid.UUID,
    request: Request,
    actor: Actor = Depends(console_people),
    db: Session = Depends(get_db),
) -> dict:
    """Who may succeed in one workspace: names, usernames and roles, never content."""
    return read_metadata(request, db, lambda: candidates.candidates(db, workspace_id))
