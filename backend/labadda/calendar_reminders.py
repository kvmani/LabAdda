"""Timed calendar alerts use the durable notification outbox and current grants."""

from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import notify, policy
from .models import CalendarEvent, User, Workspace


def process_calendar_reminders(db: Session, now: datetime) -> int:
    """Queue each timed event once per start time, within fifteen minutes of starting."""
    events = db.scalars(
        select(CalendarEvent)
        .where(
            CalendarEvent.cancelled_at.is_(None),
            CalendarEvent.all_day.is_(False),
            CalendarEvent.reminder_start_processed_at.is_distinct_from(CalendarEvent.starts_at),
            CalendarEvent.starts_at >= now,
            CalendarEvent.starts_at <= now + timedelta(minutes=15),
        )
        .order_by(CalendarEvent.starts_at, CalendarEvent.id)
        .limit(100)
        .with_for_update(skip_locked=True)
    )
    count = 0
    for event in events:
        if event.scope_kind == "personal":
            recipients = [event.owner_id]
        elif event.scope_kind == "site":
            recipients = db.scalars(select(User.id).where(User.is_active.is_(True))).all()
        else:
            workspace = db.get(Workspace, event.workspace_id)
            recipients = policy.eligible_reader_ids(db, workspace) if workspace else []
        event.reminder_start_processed_at = event.starts_at
        count += notify.create(
            db,
            recipients=recipients,
            kind="reminder",
            workspace_id=event.workspace_id,
            source_type="calendar",
            source_id=event.id,
            occurrence=event.starts_at.isoformat(),
        )
    return count
