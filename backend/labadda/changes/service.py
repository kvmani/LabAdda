"""Serialize current authority and atomically apply exactly reviewed staff changes."""

import hmac
import uuid
from contextlib import nullcontext
from datetime import date
from types import ModuleType

from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .. import audit, identity_locks, memberships, people, policy
from ..config import Settings
from ..deps import Actor
from ..errors import Conflict, Forbidden, Invalid, NotFound
from ..models import ScheduledChange, User, Workspace
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
    unit_admin,
    unit_close,
    unit_create,
    unit_merge,
    unit_move,
    unit_rename,
    unit_reopen,
    unit_split,
)
from .kinds.common import MAX_TERM
from .plan import Plan
from .requests import AddPerson, ApplyRequest, ChangeAuthority, ChangeRequest, Leave, Retire, Transfer
from .unit_requests import UnitChange

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
    "unit_create": unit_create,
    "unit_rename": unit_rename,
    "unit_move": unit_move,
    "unit_merge": unit_merge,
    "unit_split": unit_split,
    "unit_close": unit_close,
    "unit_reopen": unit_reopen,
    "unit_admin_grant": unit_admin,
    "unit_admin_revoke": unit_admin,
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


# Their one-time activation code must reach the administrator who applies them.
NOT_SCHEDULABLE = ("add_person", "reinstate")


def check_day(settings: Settings, request: ChangeRequest, day: date | None) -> None:
    """A scheduled change starts tomorrow or later, within five years, and never issues a code."""
    if day is None:
        return
    if request.kind in NOT_SCHEDULABLE:
        raise Invalid("not_schedulable", "This change issues an activation code, so it cannot be scheduled.")
    start = people.site_date(settings)
    if not start < day <= start + MAX_TERM:
        raise Invalid("invalid_date", "Choose a day after today and within five years.")


def dated(day: date | None):
    """Build and apply with the effective day as 'today' so review and run agree."""
    return people.as_of(day) if day else nullcontext()


def preview(
    db: Session, actor: Actor, settings: Settings, request: ChangeRequest, effective_on: date | None = None
) -> dict:
    """Build metadata without staff/audit writes and recheck session before delivery."""
    user = authorize(db, actor, settings)
    check_day(settings, request, effective_on)
    with dated(effective_on):
        payload = build(db, request, user.id, settings).to_dict()
    authorize(db, actor, settings)
    return payload


def successor_ids(request: ChangeRequest) -> set[uuid.UUID]:
    """Other people a retirement or leave appoints; they are locked before being given a role."""
    if isinstance(request, Retire):
        return {item.successor_id for item in request.successors}
    if isinstance(request, Leave):
        return {cover.successor_id for cover in request.acting}
    return set()


def lock_targets(db: Session, request: ChangeRequest) -> None:
    """After the admin and actor locks: workspace role locks, then the existing person row."""
    if isinstance(request, AddPerson):
        memberships.lock_workspace_roles(db, request.home_unit_id)
        return
    if isinstance(request, UnitChange):
        KINDS[request.kind].lock_scope(db, request)
        return
    scope = KINDS[request.kind].lock_scope(db, request) if request.kind != "edit_person" else None
    person_id = request.successor_id if isinstance(request, ChangeAuthority) else request.person_id
    # One ordered statement for the person and everyone the plan appoints, so two changes that
    # name the same people cannot lock them in opposite orders.
    wanted = {person_id, *successor_ids(request)}
    locked = db.scalars(
        select(User)
        .where(User.id.in_(wanted))
        .order_by(User.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    ).all()
    target = next((row for row in locked if row.id == person_id), None)
    if target is None:
        raise NotFound()
    if isinstance(request, Transfer) and scope is not None:
        transfer.require_locked_home(target, scope)


def record_plan(
    db: Session,
    actor: User,
    plan: Plan,
    reason: str,
    settings: Settings,
    person_id: uuid.UUID,
    scope_type: str = "identity",
) -> None:
    """Write parent and structured per-step audit rows within the change transaction."""
    audit.record(
        db,
        actor=actor,
        action="people.change",
        scope_type=scope_type,
        scope_id=person_id if scope_type == "workspace" else None,
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


def _reviewed(db: Session, user: User, body: ApplyRequest, settings: Settings) -> Plan:
    """Lock, rebuild and require the plan the administrator reviewed, with no blockers."""
    lock_targets(db, body.request)
    plan = build(db, body.request, user.id, settings)
    revisions = {str(identity): revision for identity, revision in body.revisions.items()}
    if not hmac.compare_digest(plan.digest, body.digest) or revisions != plan.revisions.to_dict():
        raise Conflict("plan_stale", "This record or its consequences changed. Review a fresh plan.")
    if plan.blockers:
        raise Invalid("plan_blocked", "Resolve the blocking problems before applying this change.")
    return plan


def subject_of(request: ChangeRequest) -> uuid.UUID | None:
    """The person or unit a scheduled change is about, for listing on their page."""
    for name in ("person_id", "workspace_id", "unit_id"):
        if getattr(request, name, None) is not None:
            return getattr(request, name)
    return None


def schedule(db: Session, actor: Actor, settings: Settings, body: ApplyRequest) -> dict:
    """Store a reviewed change for its day; nothing is applied and no access changes yet."""
    day = body.effective_on
    try:
        user = authorize(db, actor, settings)
        check_day(settings, body.request, day)
        with dated(day):
            plan = _reviewed(db, user, body, settings)
        row = ScheduledChange(
            kind=plan.kind,
            request=body.request.model_dump(mode="json"),
            plan_digest=plan.digest,
            effective_on=day,
            created_by=user.id,
            reason=body.reason,
            subject_id=subject_of(body.request),
            steps=[step.summary for step in plan.steps],
        )
        db.add(row)
        db.flush()
        audit.record(
            db,
            actor=user,
            action="people.schedule",
            scope_type="identity",
            target_id=row.subject_id,
            reason=body.reason,
            kind=plan.kind,
            plan_digest=plan.digest,
            effective_on=day,
            scheduled_id=row.id,
        )
        db.commit()
    except IntegrityError:
        db.rollback()
        raise Conflict("plan_stale", "Staff information changed. Review a fresh plan.") from None
    except Exception:
        db.rollback()
        raise
    return {
        "scheduled": True,
        "id": str(row.id),
        "kind": plan.kind,
        "effective_on": day.isoformat(),
        "digest": plan.digest,
    }


def _commit(
    db: Session, user: User, body: ApplyRequest, settings: Settings
) -> tuple[User | Workspace, dict, Plan]:
    plan = _reviewed(db, user, body, settings)
    person, extra = KINDS[plan.kind].apply(db, user, plan, body.request, settings, body.reason)
    if isinstance(person, Workspace):
        record_plan(db, user, plan, body.reason, settings, person.id, "workspace")
        db.commit()
        return (
            person,
            {"applied": True, "kind": plan.kind, "unit_id": str(person.id), "digest": plan.digest, **extra},
            plan,
        )
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


def is_unit(person: User | Workspace) -> bool:
    return isinstance(person, Workspace)


def revalidate(hub: Hub, person: User | Workspace, plan: Plan) -> None:
    """Refresh live delivery for the person and every identity and workspace the plan touched."""
    if isinstance(person, Workspace):
        hub.revalidate_all()  # a hierarchy change can alter what many people may read
        return
    hub.revalidate_user(person.id)
    for step in plan.steps:
        if step.target_type == "workspace":
            hub.revalidate_workspace(uuid.UUID(step.target_id))
        elif not step.target_id.startswith("new:"):
            hub.revalidate_user(uuid.UUID(step.target_id))


def apply(db: Session, actor: Actor, settings: Settings, body: ApplyRequest, hub: Hub) -> dict:
    """Rebuild under locks, reject stale review, commit once, then revalidate delivery."""
    if body.effective_on is not None:
        return schedule(db, actor, settings, body)
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
