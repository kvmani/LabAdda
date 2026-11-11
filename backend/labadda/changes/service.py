"""Serialize current authority and atomically apply exactly reviewed staff changes."""

import hmac

from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .. import audit, identity_locks, memberships, people, policy
from ..config import Settings
from ..deps import Actor
from ..errors import Conflict, Forbidden, Invalid, NotFound
from ..models import User
from ..realtime import Hub
from .kinds import edit_person
from .plan import Plan
from .requests import ApplyRequest, EditPerson


def authorize(db: Session, actor: Actor, settings: Settings) -> User:
    """Refresh authority under the shared role and user/session locks without committing."""
    db.execute(text("SET LOCAL statement_timeout = '2s'"))
    memberships.lock_admin_roles(db)
    user = identity_locks.lock_identity(db, actor, settings)
    if "people" not in policy.console_sections(db, user):
        raise Forbidden("admin_required", "Administrator access is required.")
    return user


def preview(db: Session, actor: Actor, settings: Settings, request: EditPerson) -> dict:
    """Build metadata without staff/audit writes and recheck session before delivery."""
    user = authorize(db, actor, settings)
    payload = edit_person.build(db, request, user.id).to_dict()
    authorize(db, actor, settings)
    return payload


def record_plan(db: Session, actor: User, plan: Plan, reason: str, settings: Settings) -> None:
    """Write parent and structured per-step audit rows within the edit transaction."""
    audit.record(
        db,
        actor=actor,
        action="people.change",
        scope_type="identity",
        target_id=plan.steps[0].target_id,
        reason=reason,
        kind=plan.kind,
        plan_digest=plan.digest,
        effective_on=people.site_date(settings),
    )
    for index, step in enumerate(plan.steps):
        audit.record_step(
            db,
            actor=actor,
            plan_digest=plan.digest,
            index=index,
            scope_type=step.target_type,
            target_id=step.target_id,
            reason=reason,
            before=step.before.to_dict(),
            after=step.after.to_dict(),
        )


def apply(db: Session, actor: Actor, settings: Settings, body: ApplyRequest, hub: Hub) -> dict:
    """Rebuild under locks, reject stale review, commit once, then revalidate delivery."""
    try:
        user = authorize(db, actor, settings)
        target = db.scalar(select(User).where(User.id == body.request.person_id).with_for_update())
        if target is None:
            raise NotFound()
        plan = edit_person.build(db, body.request, user.id)
        revisions = {str(identity): revision for identity, revision in body.revisions.items()}
        if not hmac.compare_digest(plan.digest, body.digest) or revisions != plan.revisions.to_dict():
            raise Conflict("plan_stale", "This record or its consequences changed. Review a fresh plan.")
        if plan.blockers:
            raise Invalid("plan_blocked", "Resolve the blocking problems before applying this change.")
        person = edit_person.apply(db, user, plan)
        record_plan(db, user, plan, body.reason, settings)
        db.commit()
        receipt = {
            "applied": True,
            "person_id": str(person.id),
            "revision": person.revision,
            "digest": plan.digest,
        }
    except IntegrityError:
        db.rollback()
        raise Conflict("plan_stale", "Staff information changed. Review a fresh plan.") from None
    except Exception:
        db.rollback()
        raise
    hub.revalidate_user(person.id)
    authorize(db, actor, settings)
    return receipt
