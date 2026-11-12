"""Scheduled staff changes (PO-06): list, cancel and the due-time runner.

At the start of the effective day the runner rebuilds the plan under the same locks and guards as
a live apply. It applies only a plan identical to the one reviewed; anything else is left unapplied
as "needs review" with a plain reason, because the reviewed consequences no longer hold.
"""

from __future__ import annotations

import hmac
import logging
import uuid
from datetime import datetime

from pydantic import TypeAdapter
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from .. import audit, memberships, people, policy
from ..config import Settings
from ..errors import ApiError, Conflict, NotFound
from ..models import ScheduledChange, User
from ..realtime import Hub
from ..security import utcnow
from ..serialize import iso
from . import service, unit_scope
from .requests import ChangeRequest

log = logging.getLogger("labadda.changes")
MAX_LISTED = 200
CHANGED = (
    "Something this change depends on was changed after it was scheduled. Review it and schedule it again."
)


class NeedsReview(Exception):
    """The reviewed plan no longer holds; the message is shown to staff as written."""


def _visible_to(db: Session, viewer: User, row: ScheduledChange) -> bool:
    """A unit administrator sees only changes that stay inside their branch, judged from now."""
    reach = unit_scope.reach_for(db, viewer)
    if reach is None:
        return True
    return reach.plainly_inside(db, TypeAdapter(ChangeRequest).validate_python(row.request))


def listing(db: Session, person_id: uuid.UUID | None = None, viewer: User | None = None) -> dict:
    """Pending and needs-review changes, soonest first; names and dates only.

    Pass ``viewer`` when the reader is a unit administrator, to list only changes within their reach.
    """
    query = select(ScheduledChange, User.display_name).join(User, User.id == ScheduledChange.created_by)
    query = query.where(ScheduledChange.state.in_(("pending", "needs_review")))
    if person_id is not None:
        query = query.where(ScheduledChange.subject_id == person_id)
    query = query.order_by(ScheduledChange.effective_on, ScheduledChange.created_at)
    rows = db.execute(query.limit(MAX_LISTED if viewer is None else 1000)).all()
    if viewer is not None:
        rows = [(row, name) for row, name in rows if _visible_to(db, viewer, row)][:MAX_LISTED]
    return {
        "items": [
            {
                "id": str(row.id),
                "kind": row.kind,
                "effective_on": row.effective_on.isoformat(),
                "state": row.state,
                "note": row.note,
                "reason": row.reason,
                "subject_id": str(row.subject_id) if row.subject_id else None,
                "steps": row.steps,
                "created_by": name,
                "created_at": iso(row.created_at),
            }
            for row, name in rows
        ]
    }


def cancel(db: Session, actor: User, change_id: uuid.UUID, reason: str) -> dict:
    """Withdraw a pending or needs-review change; an applied or cancelled one is final."""
    row = db.scalar(select(ScheduledChange).where(ScheduledChange.id == change_id).with_for_update())
    if row is None or not _visible_to(db, actor, row):
        raise NotFound()
    if row.state not in ("pending", "needs_review"):
        raise Conflict("not_pending", "This change has already been applied or cancelled.")
    before = row.state
    row.state = "cancelled"
    audit.record(
        db,
        actor=actor,
        action="people.schedule_cancel",
        scope_type="identity",
        target_id=row.subject_id,
        reason=reason,
        kind=row.kind,
        plan_digest=row.plan_digest,
        scheduled_id=row.id,
        before=before,
    )
    db.commit()
    return {"cancelled": True, "id": str(row.id)}


def _attempt(db: Session, settings: Settings, row: ScheduledChange, now: datetime):
    """Re-preview and apply under the live protocol's locks; raise NeedsReview if it no longer fits."""
    memberships.lock_admin_roles(db)
    actor = db.scalar(
        select(User)
        .where(User.id == row.created_by)
        .with_for_update(key_share=True)
        .execution_options(populate_existing=True)
    )
    if actor is None or "people" not in policy.console_sections(db, actor):
        raise NeedsReview("The administrator who scheduled this change can no longer make it.")
    request = TypeAdapter(ChangeRequest).validate_python(row.request)
    with people.as_of(row.effective_on):
        service.lock_targets(db, request)
        plan = service.build(db, request, actor.id, settings)
        if plan.blockers:
            raise NeedsReview(plan.blockers[0].message)
        if not hmac.compare_digest(plan.digest, row.plan_digest):
            raise NeedsReview(CHANGED)
        person, _extra = service.KINDS[plan.kind].apply(db, actor, plan, request, settings, row.reason)
        scope = "workspace" if service.is_unit(person) else "identity"
        service.record_plan(db, actor, plan, row.reason, settings, person.id, scope)
    audit.record(
        db,
        actor=actor,
        action="people.schedule_apply",
        scope_type=scope,
        scope_id=person.id if scope == "workspace" else None,
        target_id=person.id,
        reason=row.reason,
        kind=plan.kind,
        plan_digest=plan.digest,
        scheduled_id=row.id,
    )
    row.state = "applied"
    row.applied_at = now
    return person, plan


def _flag(db: Session, change_id: uuid.UUID, note: str) -> None:
    """Leave the change unapplied and ask staff to look at it (attention item PO-22)."""
    row = db.scalar(
        select(ScheduledChange)
        .where(ScheduledChange.id == change_id, ScheduledChange.state == "pending")
        .with_for_update()
    )
    if row is None:
        return
    row.state = "needs_review"
    row.note = note
    audit.record(
        db,
        actor=None,
        action="people.schedule_review",
        scope_type="identity",
        target_id=row.subject_id,
        reason=note,
        kind=row.kind,
        scheduled_id=row.id,
    )
    db.commit()


def _run_one(db: Session, settings: Settings, hub: Hub | None, change_id: uuid.UUID, now: datetime) -> bool:
    try:
        row = db.scalar(
            select(ScheduledChange)
            .where(ScheduledChange.id == change_id, ScheduledChange.state == "pending")
            .with_for_update(skip_locked=True)
        )
        if row is None:
            db.rollback()
            return False
        person, plan = _attempt(db, settings, row, now)
        db.commit()
    except Exception as error:
        db.rollback()
        if isinstance(error, NeedsReview | ApiError):
            note = str(error) if isinstance(error, NeedsReview) else error.message
            if isinstance(error, NotFound):
                note = "A person or unit this change refers to is no longer available."
        else:
            log.exception("changes.scheduled_failed", extra={"scheduled_id": str(change_id)})
            note = CHANGED
        _flag(db, change_id, note)
        return False
    if hub is not None:
        service.revalidate(hub, person, plan)
    return True


def run_due(
    db: Session, settings: Settings, hub: Hub | None = None, now: datetime | None = None, batch: int = 50
) -> int:
    """Apply every pending change whose day has started; safe to run twice or concurrently."""
    now = now or utcnow()
    today = people.site_date(settings, now=now)
    due = list(
        db.scalars(
            select(ScheduledChange.id)
            .where(ScheduledChange.state == "pending", ScheduledChange.effective_on <= today)
            .order_by(ScheduledChange.effective_on, ScheduledChange.created_at, ScheduledChange.id)
            .limit(batch)
        )
    )
    db.rollback()
    return sum(_run_one(db, settings, hub, change_id, now) for change_id in due)


def run_job(factory: sessionmaker, settings: Settings, hub: Hub | None = None):
    """Scheduler step: one bounded pass per tick."""

    def run_scheduled_changes() -> None:
        with factory() as db:
            run_due(db, settings, hub)

    return run_scheduled_changes
