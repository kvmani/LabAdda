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
from .kinds import (
    add_person,
    additional_charge,
    change_authority,
    edit_person,
    leave,
    promote,
    reinstate,
    retire,
    return_from_leave,
    suspend,
    transfer,
)
from .plan import Plan
from .requests import AddPerson, ApplyRequest, ChangeAuthority, ChangeRequest, Transfer

KINDS: dict[str, ModuleType] = {
    "add_person": add_person,
    "edit_person": edit_person,
    "transfer": transfer,
    "promote": promote,
    "change_authority": change_authority,
    "additional_charge": additional_charge,
    "leave": leave,
    "return": return_from_leave,
    "retire": retire,
    "suspend": suspend,
    "reinstate": reinstate,
}


def authorize(db: Session, actor: Actor, settings: Settings) -> User:
    """Refresh authority under the shared role and user/session locks without committing."""
    # The short bound is for waiting on authority locks only; the change's own writes and
    # commit run under the connection's normal limit. A failure aborts the transaction,
    # which discards the local setting, so restoring is needed only on success.
    previous = db.scalar(text("select current_setting('statement_timeout')"))
    db.execute(text("SET LOCAL statement_timeout = '2s'"))
    memberships.lock_admin_roles(db)
    user = identity_locks.lock_identity(db, actor, settings)
    if "people" not in policy.console_sections(db, user):
        raise Forbidden("admin_required", "Administrator access is required.")
    db.execute(text("select set_config('statement_timeout', :value, true)"), {"value": previous})
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
    if isinstance(request, AddPerson):
        memberships.lock_workspace_roles(db, request.home_unit_id)
        return
    scope = KINDS[request.kind].lock_scope(db, request) if request.kind != "edit_person" else None
    person_id = request.successor_id if isinstance(request, ChangeAuthority) else request.person_id
    target = db.scalar(
        select(User).where(User.id == person_id).with_for_update().execution_options(populate_existing=True)
    )
    if target is None:
        raise NotFound()
    if isinstance(request, Transfer) and scope is not None:
        transfer.require_locked_home(target, scope)


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


def _commit(db: Session, user: User, body: ApplyRequest, settings: Settings) -> tuple[User, dict, Plan]:
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
    return person, receipt, plan


def revalidate(hub: Hub, person: User, plan: Plan) -> None:
    """Refresh live delivery for the person and every identity and workspace the plan touched."""
    hub.revalidate_user(person.id)
    for step in plan.steps:
        if step.target_type == "workspace":
            hub.revalidate_workspace(uuid.UUID(step.target_id))
        elif not step.target_id.startswith("new:"):
            hub.revalidate_user(uuid.UUID(step.target_id))


def apply(db: Session, actor: Actor, settings: Settings, body: ApplyRequest, hub: Hub) -> dict:
    """Rebuild under locks, reject stale review, commit once, then revalidate delivery."""
    try:
        user = authorize(db, actor, settings)
        person, receipt, plan = _commit(db, user, body, settings)
    except IntegrityError:
        db.rollback()
        raise Conflict("plan_stale", "Staff information changed. Review a fresh plan.") from None
    except Exception:
        db.rollback()
        raise
    # The change is durable: the receipt (with any one-time code) must reach the person who
    # applied it even if their session ends now, because a retry can only return plan_stale.
    revalidate(hub, person, plan)
    return receipt
