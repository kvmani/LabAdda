"""Serialize current authority and atomically apply exactly reviewed staff changes."""

import hmac
import uuid
from types import ModuleType

from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .. import audit, identity_locks, memberships, people, policy
from ..config import Settings
from ..deps import Actor
from ..errors import Conflict, Forbidden, Invalid, NotFound
from ..models import User
from ..realtime import Hub
from .kinds import add_person, edit_person, transfer
from .plan import Plan
from .requests import AddPerson, ApplyRequest, ChangeRequest, Transfer

KINDS: dict[str, ModuleType] = {"add_person": add_person, "edit_person": edit_person, "transfer": transfer}


def authorize(db: Session, actor: Actor, settings: Settings) -> User:
    """Refresh authority under the shared role and user/session locks without committing."""
    db.execute(text("SET LOCAL statement_timeout = '2s'"))
    memberships.lock_admin_roles(db)
    user = identity_locks.lock_identity(db, actor, settings)
    if "people" not in policy.console_sections(db, user):
        raise Forbidden("admin_required", "Administrator access is required.")
    return user


def build(db: Session, request: ChangeRequest, actor_id: uuid.UUID, settings: Settings) -> Plan:
    """Dispatch to the kind's builder; every kind reads current state only."""
    return KINDS[request.kind].build(db, request, actor_id, settings)


def preview(db: Session, actor: Actor, settings: Settings, request: ChangeRequest) -> dict:
    """Build metadata without staff/audit writes and recheck session before delivery."""
    user = authorize(db, actor, settings)
    payload = build(db, request, user.id, settings).to_dict()
    authorize(db, actor, settings)
    return payload


def lock_targets(db: Session, request: ChangeRequest) -> None:
    """After the admin and actor locks: workspace role locks, then the existing person row."""
    if isinstance(request, Transfer):
        transfer.lock_scope(db, request)
    if isinstance(request, AddPerson):
        memberships.lock_workspace_roles(db, request.home_unit_id)
        return
    target = db.scalar(select(User).where(User.id == request.person_id).with_for_update())
    if target is None:
        raise NotFound()


def record_plan(
    db: Session, actor: User, plan: Plan, reason: str, settings: Settings, person_id: uuid.UUID
) -> None:
    """Write parent and structured per-step audit rows within the change transaction."""
    audit.record(
        db,
        actor=actor,
        action="people.change",
        scope_type="identity",
        target_id=person_id,
        reason=reason,
        kind=plan.kind,
        plan_digest=plan.digest,
        effective_on=people.site_date(settings),
    )
    for index, step in enumerate(plan.steps):
        # An onboarding plan names the not-yet-created account; the audit names the real one.
        target_id = str(person_id) if step.target_id.startswith("new:") else step.target_id
        audit.record_step(
            db,
            actor=actor,
            plan_digest=plan.digest,
            index=index,
            scope_type=step.target_type,
            target_id=target_id,
            reason=reason,
            before=step.before.to_dict(),
            after=step.after.to_dict(),
        )


def _commit(db: Session, user: User, body: ApplyRequest, settings: Settings) -> tuple[User, dict]:
    lock_targets(db, body.request)
    plan = build(db, body.request, user.id, settings)
    revisions = {str(identity): revision for identity, revision in body.revisions.items()}
    if not hmac.compare_digest(plan.digest, body.digest) or revisions != plan.revisions.to_dict():
        raise Conflict("plan_stale", "This record or its consequences changed. Review a fresh plan.")
    if plan.blockers:
        raise Invalid("plan_blocked", "Resolve the blocking problems before applying this change.")
    person, extra = KINDS[plan.kind].apply(db, user, plan, body.request, settings, body.reason)
    record_plan(db, user, plan, body.reason, settings, person.id)
    db.commit()
    receipt = {
        "applied": True,
        "kind": plan.kind,
        "person_id": str(person.id),
        "revision": person.revision,
        "digest": plan.digest,
        **extra,
    }
    return person, receipt


def apply(db: Session, actor: Actor, settings: Settings, body: ApplyRequest, hub: Hub) -> dict:
    """Rebuild under locks, reject stale review, commit once, then revalidate delivery."""
    try:
        user = authorize(db, actor, settings)
        person, receipt = _commit(db, user, body, settings)
    except IntegrityError:
        db.rollback()
        raise Conflict("plan_stale", "Staff information changed. Review a fresh plan.") from None
    except Exception:
        db.rollback()
        raise
    hub.revalidate_user(person.id)
    authorize(db, actor, settings)
    return receipt
