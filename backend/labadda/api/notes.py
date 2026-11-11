"""My Notes: owner-only personal notes and reminders (S3)."""

from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..deps import Actor, current_actor, get_db
from ..errors import Invalid, NotFound
from ..models import Note
from ..security import utcnow
from ..serialize import iso

router = APIRouter(prefix="/notes", tags=["notes"])


class NoteBody(BaseModel):
    title: str = Field(default="", max_length=200)
    body: str = Field(default="", max_length=20_000)
    due_at: datetime | None = None
    remind_at: datetime | None = None


def _json(n: Note) -> dict:
    return {
        "id": str(n.id),
        "title": n.title,
        "body": n.body,
        "due_at": iso(n.due_at),
        "remind_at": iso(n.remind_at),
        "created_at": iso(n.created_at),
        "updated_at": iso(n.updated_at),
    }


def _validate(body: NoteBody):
    if not body.title.strip() and not body.body.strip():
        raise Invalid("empty_note", "Write a title or some text.")
    for v in (body.due_at, body.remind_at):
        if v is not None and v.tzinfo is None:
            raise Invalid("timezone_required", "Times must include a UTC offset.")
    if body.due_at and body.remind_at and body.remind_at > body.due_at:
        raise Invalid("remind_after_due", "The reminder must be at or before the due time.")


def _own(db: Session, actor: Actor, note_id: uuid.UUID) -> Note:
    note = db.get(Note, note_id)
    if note is None or note.owner_id != actor.id:
        raise NotFound()  # identical to unknown ID, including for administrators
    return note


@router.get("")
def list_notes(actor: Actor = Depends(current_actor), db: Session = Depends(get_db)):
    rows = db.scalars(select(Note).where(Note.owner_id == actor.id).order_by(Note.updated_at.desc())).all()
    return {"notes": [_json(n) for n in rows]}


@router.get("/upcoming")
def upcoming_notes(actor: Actor = Depends(current_actor), db: Session = Depends(get_db)):
    rows = db.scalars(
        select(Note)
        .where(Note.owner_id == actor.id, Note.due_at.is_not(None), Note.due_at >= utcnow())
        .order_by(Note.due_at)
        .limit(20)
    ).all()
    return {
        "items": [
            {
                "id": str(n.id),
                "source": "note",
                "title": n.title or n.body[:120],
                "due_at": iso(n.due_at),
                "remind_at": iso(n.remind_at),
            }
            for n in rows
        ]
    }


@router.post("", status_code=201)
def create_note(body: NoteBody, actor: Actor = Depends(current_actor), db: Session = Depends(get_db)):
    _validate(body)
    note = Note(
        owner_id=actor.id,
        title=body.title.strip(),
        body=body.body,
        due_at=body.due_at,
        remind_at=body.remind_at,
    )
    db.add(note)
    db.commit()
    return _json(note)


@router.get("/{note_id}")
def get_note(note_id: uuid.UUID, actor: Actor = Depends(current_actor), db: Session = Depends(get_db)):
    return _json(_own(db, actor, note_id))


@router.put("/{note_id}")
def update_note(
    note_id: uuid.UUID, body: NoteBody, actor: Actor = Depends(current_actor), db: Session = Depends(get_db)
):
    note = _own(db, actor, note_id)
    _validate(body)
    if body.remind_at != note.remind_at:
        note.reminder_processed_at = None
    note.title, note.body, note.due_at, note.remind_at = (
        body.title.strip(),
        body.body,
        body.due_at,
        body.remind_at,
    )
    note.updated_at = utcnow()
    db.commit()
    return _json(note)


@router.delete("/{note_id}")
def delete_note(note_id: uuid.UUID, actor: Actor = Depends(current_actor), db: Session = Depends(get_db)):
    note = _own(db, actor, note_id)
    db.delete(note)
    db.commit()
    return {"ok": True}
