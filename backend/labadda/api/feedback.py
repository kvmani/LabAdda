"""Feedback button: any signed-in person sends; administrators read, triage and download (Pilot)."""

from __future__ import annotations

import base64
import binascii
import json
import uuid
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, File, Form, Query, Request, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from .. import audit, feedback, feedback_mail
from ..config import Settings
from ..deps import PANEL_HEADER, Actor, current_actor, get_db, get_settings, require_console
from ..errors import Conflict, Invalid, NotFound, Unauthenticated
from ..models import Asset, Feedback, FeedbackMail
from ..security import utcnow
from .files import PROTECTED_HEADERS

router = APIRouter(tags=["feedback"])
console_feedback = require_console("feedback", admin_only=True)
PAGE_SIZE = 25
MAX_PAGE = 100
Status = Literal["new", "seen", "resolved"]
Category = Literal["problem", "suggestion", "question"]


def person_actor(request: Request, actor: Actor = Depends(current_actor)) -> Actor:
    """A normal signed-in person; a board-only screen is never a person, even with a stray cookie."""
    if request.headers.get(PANEL_HEADER) or actor.is_panel:
        raise Unauthenticated()
    return actor


async def _read(upload: UploadFile) -> feedback.Upload:
    limit = feedback.MAX_FILE_BYTES
    chunks, total = [], 0
    while chunk := await upload.read(1024 * 256):
        total += len(chunk)
        if total > limit:
            raise Invalid("file_too_large", f"Each file must be {limit // (1024 * 1024)} MiB or smaller.")
        chunks.append(chunk)
    return feedback.Upload(upload.filename, upload.content_type, b"".join(chunks))


@router.get("/feedback/form")
def form_facts(actor: Actor = Depends(person_actor), settings: Settings = Depends(get_settings)) -> dict:
    """What the server will record, so the form can show it before anything is sent."""
    facts = feedback.metadata_preview(actor.user)
    return {
        **facts,
        "max_message": feedback.MAX_MESSAGE,
        "max_files": feedback.MAX_FILES,
        "max_file_bytes": feedback.MAX_FILE_BYTES,
        "max_total_bytes": feedback.MAX_TOTAL_BYTES,
        "email_copy": settings.mail_configured,
    }


@router.post("/feedback", status_code=201)
async def send_feedback(
    request: Request,
    *,
    client_id: str = Form(...),
    category: str = Form(...),
    message: str = Form(...),
    route: str | None = Form(default=None, max_length=400),
    screen: str | None = Form(default=None, max_length=20),
    files: list[UploadFile] = File(default_factory=list),
    actor: Actor = Depends(person_actor),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> dict:
    if len(files) > feedback.MAX_FILES:
        raise Invalid("too_many_attachments", f"Attach at most {feedback.MAX_FILES} files.")
    uploads = [await _read(f) for f in files]
    row = await run_in_threadpool(
        feedback.submit,
        db,
        request.app.state.assets,
        actor,
        settings,
        client_id=client_id,
        category=category,
        message=message,
        route=route,
        screen=screen,
        user_agent=request.headers.get("user-agent"),
        files=uploads,
        session_factory=request.app.state.session_factory,
    )
    return feedback.sent_json(row)


class TriageBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_revision: int = Field(ge=1)
    status: Status | None = None
    admin_note: str | None = Field(default=None, max_length=2000)


def _encode(row: Feedback) -> str:
    return (
        base64.urlsafe_b64encode(json.dumps([row.created_at.isoformat(), str(row.id)]).encode())
        .decode()
        .rstrip("=")
    )


def _decode(cursor: str) -> tuple[datetime, uuid.UUID]:
    try:
        created, ident = json.loads(base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4)))
        return datetime.fromisoformat(created), uuid.UUID(ident)
    except (ValueError, TypeError, binascii.Error):
        raise Invalid("invalid_cursor", "That page of feedback is no longer available.") from None


def _row(db: Session, feedback_id: uuid.UUID, *, lock: bool = False) -> Feedback:
    query = select(Feedback).where(Feedback.id == feedback_id)
    row = db.scalar(query.with_for_update() if lock else query)
    if row is None:
        raise NotFound()
    return row


@router.get("/admin/feedback")
def list_feedback(
    status: Status | None = None,
    category: Category | None = None,
    username: str | None = Query(default=None, max_length=64),
    cursor: str | None = Query(default=None, max_length=200),
    limit: int = Query(default=PAGE_SIZE, ge=1, le=MAX_PAGE),
    *,
    actor: Actor = Depends(console_feedback),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> dict:
    """Newest first, without message text: the text is read, and audited, one message at a time."""
    query = select(Feedback).order_by(Feedback.created_at.desc(), Feedback.id.desc()).limit(limit + 1)
    for column, value in ((Feedback.status, status), (Feedback.category, category)):
        if value:
            query = query.where(column == value)
    if username:
        query = query.where(Feedback.username == username.strip().lower())
    if cursor:
        created, ident = _decode(cursor)
        query = query.where(
            or_(Feedback.created_at < created, and_(Feedback.created_at == created, Feedback.id < ident))
        )
    found = db.scalars(query).all()
    page = found[:limit]
    ids = [r.id for r in page]
    counts = feedback.attachment_counts(db, ids)
    mails = {
        m.feedback_id: m for m in db.scalars(select(FeedbackMail).where(FeedbackMail.feedback_id.in_(ids)))
    }
    outbox = feedback_mail.outbox_counts(db)
    return {
        "items": [
            feedback.summary_json(r, counts.get(r.id, 0), mails.get(r.id), settings.mail_configured)
            for r in page
        ],
        "next_cursor": _encode(page[-1]) if len(found) > limit else None,
        "email": {
            "configured": settings.mail_configured,
            "queued": outbox["queued"],
            "failed": outbox["failed"],
        },
    }


def _detail(db: Session, row: Feedback, settings: Settings) -> dict:
    assets = feedback.attachments(db, [row.id])[row.id]
    return feedback.detail_json(row, assets, db.get(FeedbackMail, row.id), settings) | {
        "revision": row.revision
    }


@router.get("/admin/feedback/{feedback_id}")
def read_feedback(
    feedback_id: uuid.UUID,
    actor: Actor = Depends(console_feedback),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> dict:
    """Administrators may read this: the sender chose to send it to them. Every read is recorded."""
    row = _row(db, feedback_id)
    audit.record(db, actor=actor.user, action="feedback.read", scope_type="site", target_id=row.id)
    result = _detail(db, row, settings)
    db.commit()
    return result


@router.patch("/admin/feedback/{feedback_id}")
def triage_feedback(
    feedback_id: uuid.UUID,
    body: TriageBody,
    actor: Actor = Depends(console_feedback),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> dict:
    row = _row(db, feedback_id, lock=True)
    if row.revision != body.expected_revision:
        raise Conflict("feedback_changed", "Someone else changed this message. Reload it and try again.")
    note = body.admin_note.strip() if body.admin_note is not None else row.admin_note
    new_status = body.status or row.status
    if new_status == row.status and (note or None) == (row.admin_note or None):
        return _detail(db, row, settings)
    audit.record(
        db,
        actor=actor.user,
        action="feedback.update",
        scope_type="site",
        target_id=row.id,
        before=row.status,
        after=new_status,
        note_changed=(note or None) != (row.admin_note or None),
    )
    row.status, row.admin_note = new_status, note or None
    row.revision += 1
    row.handled_by, row.handled_at = actor.user.id, utcnow()
    db.commit()
    return _detail(db, row, settings)


@router.post("/admin/feedback/{feedback_id}/resend")
def resend_email(
    feedback_id: uuid.UUID,
    actor: Actor = Depends(console_feedback),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> dict:
    row = _row(db, feedback_id, lock=True)
    mail = db.get(FeedbackMail, row.id, with_for_update=True)
    if mail is None or mail.status != "failed":
        raise Conflict("not_failed", "Only an e-mail that failed can be queued again.")
    feedback_mail.requeue(db, row.id)
    audit.record(db, actor=actor.user, action="feedback.resend", scope_type="site", target_id=row.id)
    db.commit()
    return _detail(db, row, settings)


def _attachment(db: Session, feedback_id: uuid.UUID, asset_id: uuid.UUID) -> Asset:
    asset = db.get(Asset, asset_id)
    if asset is None or asset.feedback_id != feedback_id:
        raise NotFound()
    return asset


@router.get("/admin/feedback/{feedback_id}/attachments/{asset_id}")
def download_attachment(
    feedback_id: uuid.UUID,
    asset_id: uuid.UUID,
    request: Request,
    actor: Actor = Depends(console_feedback),
    db: Session = Depends(get_db),
):
    asset = _attachment(db, feedback_id, asset_id)
    path = request.app.state.assets.path(asset.storage_key)
    if not path.exists():
        raise NotFound()
    audit.record(
        db, actor=actor.user, action="feedback.attachment_read", scope_type="site", target_id=feedback_id
    )
    db.commit()
    disposition = "inline" if asset.media_type.startswith("image/") else "attachment"
    return FileResponse(
        path,
        media_type=asset.media_type,
        filename=asset.display_name,
        content_disposition_type=disposition,
        headers=PROTECTED_HEADERS,
    )


@router.get("/admin/feedback/{feedback_id}/attachments/{asset_id}/preview")
def attachment_preview(
    feedback_id: uuid.UUID,
    asset_id: uuid.UUID,
    request: Request,
    actor: Actor = Depends(console_feedback),
    db: Session = Depends(get_db),
):
    asset = _attachment(db, feedback_id, asset_id)
    path = request.app.state.assets.path(asset.storage_key, preview=True)
    if not asset.has_preview or not path.exists():
        raise NotFound()
    return FileResponse(path, media_type="image/png", headers=PROTECTED_HEADERS)
