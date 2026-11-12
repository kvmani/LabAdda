"""Administrator-only reviewed staff changes; clients never supply executable plans."""

import uuid

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from ..changes import activation, bulk, candidates, import_report, importer, service
from ..changes.requests import ApplyRequest, PreviewRequest, ReissueRequest
from ..deps import Actor, get_db, get_settings, require_console
from ..errors import ApiError, Invalid
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
        return service.preview(db, actor, get_settings(request), body.request, body.effective_on)
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


@router.get("/import/template")
def import_template(actor: Actor = Depends(console_people)) -> Response:
    """The column layout with one fictional example row."""
    return Response(
        importer.TEMPLATE,
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": 'attachment; filename="staff-list-template.csv"',
            "Cache-Control": "no-store",
        },
    )


async def _read_csv(request: Request) -> bytes:
    """Refuse a wrong type or oversized body before reading it all; the bytes are never stored."""
    if request.headers.get("content-type", "").split(";")[0].strip().lower() != "text/csv":
        raise Invalid("import_not_csv", "Upload a CSV file (.csv).")
    declared = request.headers.get("content-length", "")
    if declared.isdigit() and int(declared) > importer.MAX_BYTES:
        raise importer.UploadTooLarge()
    chunks, total = [], 0
    async for chunk in request.stream():
        total += len(chunk)
        if total > importer.MAX_BYTES:
            raise importer.UploadTooLarge()
        chunks.append(chunk)
    return b"".join(chunks)


def _import_report(db: Session, actor: Actor, settings, data: bytes) -> dict:
    user = service.authorize(db, actor, settings)
    payload = import_report.build(db, data, user.id, settings)
    service.authorize(db, actor, settings)
    return payload


@router.post("/import/preview")
async def preview_import(
    request: Request,
    actor: Actor = Depends(console_people),
    db: Session = Depends(get_db),
) -> dict:
    """Dry-run a staff-list CSV: what would be added, changed or moved, and what is wrong."""
    data = await _read_csv(request)
    try:
        return await run_in_threadpool(_import_report, db, actor, get_settings(request), data)
    except DBAPIError:
        db.rollback()
        raise ApiError(
            "changes_unavailable", "Staff changes are unavailable. Try again.", status=503
        ) from None


@router.post("/bulk/preview")
def preview_bulk(
    body: bulk.BulkPreview,
    request: Request,
    actor: Actor = Depends(console_people),
    db: Session = Depends(get_db),
) -> dict:
    """Review the selected changes together without writing anything."""
    try:
        return bulk.preview(db, actor, get_settings(request), body)
    except DBAPIError:
        db.rollback()
        raise ApiError(
            "changes_unavailable", "Staff changes are unavailable. Try again.", status=503
        ) from None


@router.post("/bulk/apply")
def apply_bulk(
    body: bulk.BulkApply,
    request: Request,
    actor: Actor = Depends(console_people),
    db: Session = Depends(get_db),
) -> dict:
    """Commit every selected change together, or none."""
    try:
        return bulk.apply(db, actor, get_settings(request), body, request.app.state.hub)
    except DBAPIError:
        db.rollback()
        raise ApiError(
            "changes_unavailable",
            "The changes could not be confirmed. Reload the people list before retrying.",
            status=503,
        ) from None
