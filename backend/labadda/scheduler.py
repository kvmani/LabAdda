"""Reminder runner. Safe to run repeatedly or concurrently: uniqueness keys dedupe."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from . import notify, policy
from .models import Note, Post, Workspace
from .security import utcnow

log = logging.getLogger("labadda.scheduler")


def process_due_reminders(db: Session, now: datetime | None = None, batch: int = 100) -> int:
    now = now or utcnow()
    created = 0
    posts = db.scalars(select(Post).where(Post.remind_at.is_not(None), Post.remind_at <= now,
                                          Post.reminder_processed_at.is_(None))
                       .order_by(Post.remind_at).limit(batch).with_for_update(skip_locked=True)).all()
    for post in posts:
        if post.deleted_at is None:
            ws = db.get(Workspace, post.workspace_id)
            # Eligibility is evaluated now, so members removed before delivery get nothing.
            recipients = policy.eligible_reader_ids(db, ws)
            created += notify.create(db, recipients=recipients, kind="reminder", workspace_id=ws.id,
                                     source_type="post", source_id=post.id, occurrence=post.remind_at.isoformat())
        post.reminder_processed_at = now
    notes = db.scalars(select(Note).where(Note.remind_at.is_not(None), Note.remind_at <= now,
                                          Note.reminder_processed_at.is_(None))
                       .order_by(Note.remind_at).limit(batch).with_for_update(skip_locked=True)).all()
    for note in notes:
        created += notify.create(db, recipients=[note.owner_id], kind="reminder", workspace_id=None,
                                 source_type="note", source_id=note.id, occurrence=note.remind_at.isoformat())
        note.reminder_processed_at = now
    db.commit()
    return created


async def run_forever(factory: sessionmaker, interval: int, on_tick=None) -> None:
    while True:
        try:
            with factory() as db:
                count = await asyncio.to_thread(process_due_reminders, db)
                if count:
                    log.info("reminders.delivered", extra={"count": count})
            if on_tick:
                await asyncio.to_thread(on_tick)
        except asyncio.CancelledError:
            raise
        except Exception:  # keep the runner alive; next tick retries
            log.exception("reminders.failed")
        await asyncio.sleep(interval)
