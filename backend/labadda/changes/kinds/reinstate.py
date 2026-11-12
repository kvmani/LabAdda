"""PO-18: back to invited with a new activation code; previous access is never restored by itself."""

import uuid

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from ... import policy, positions
from ...config import Settings
from ...credentials import issue_credential
from ...models import AuditEvent, CredentialToken, User
from ...security import utcnow
from ...serialize import iso
from ..actions import Action, Draft, end_position, set_role, set_status
from ..plan import Blocker, Plan, Snapshot, Step, Warning
from ..requests import Reinstate
from .common import load_person, lock_person_scope, named, today

DEPARTED = {"suspended", "retired", "left"}
MAX_PLACES = 10


def lock_scope(db: Session, request: Reinstate) -> None:
    lock_person_scope(db, request.person_id)


def last_placement(db: Session, person: User) -> list[str]:
    """Workspace names and roles from current grants and the last departure plan's removals."""
    places = dict(policy.direct_grants(db, person.id))
    parent = db.scalar(
        select(AuditEvent)
        .where(
            AuditEvent.action == "people.change",
            AuditEvent.target_id == str(person.id),
            AuditEvent.detail["kind"].astext.in_(("retire", "suspend")),
        )
        .order_by(AuditEvent.id.desc())
        .limit(1)
    )
    if parent is not None:
        steps = db.scalars(
            select(AuditEvent).where(
                AuditEvent.action == "people.change_step",
                AuditEvent.scope_type == "workspace",
                AuditEvent.detail["plan_digest"].astext == parent.detail.get("plan_digest"),
            )
        )
        for step in steps:
            before = step.detail.get("before", {}).get("role")
            if before in ("member", "steward") and step.detail.get("after", {}).get("role") is None:
                places.setdefault(uuid.UUID(step.target_id), before)
    spaces = named(db, set(places))
    return sorted(f"{spaces[key].name} ({role})" for key, role in places.items() if key in spaces)[
        :MAX_PLACES
    ]


def _credential(person: User, receipt: dict, settings: Settings) -> Action:
    def run(db: Session, actor: User, reason: str) -> None:
        person.password_hash = None
        # Codes issued before the departure must not reopen the account alongside the new one.
        db.execute(
            update(CredentialToken)
            .where(CredentialToken.user_id == person.id, CredentialToken.used_at.is_(None))
            .values(used_at=utcnow())
        )
        code, credential = issue_credential(db, person, "activation", actor, settings)
        receipt["activation"] = {"code": code, "expires_at": iso(credential.expires_at)}

    summary = "Issue a new one-time activation code; the old password stops working"
    return Action(
        Step(
            "identity",
            str(person.id),
            summary,
            Snapshot({"activation": None}),
            Snapshot({"activation": "issued"}),
        ),
        run,
    )


def _admin(person: User) -> Action:
    def run(db: Session, actor: User, reason: str) -> None:
        person.is_admin = False

    summary = f"Do not restore the administrator role of {person.display_name}"
    return Action(
        Step(
            "identity", str(person.id), summary, Snapshot({"is_admin": True}), Snapshot({"is_admin": False})
        ),
        run,
    )


def draft(db: Session, request: Reinstate, settings: Settings, receipt: dict) -> Draft:
    person = load_person(db, request.person_id)
    result = Draft(person, affected_people=0)
    if person.status not in DEPARTED:
        result.blockers.append(
            Blocker("not_departed", "Only suspended, retired or departed people can be reinstated.")
        )
    grants = policy.direct_grants(db, person.id)
    held = positions.current(db, user_id=person.id)
    spaces = named(db, set(grants) | {row.workspace_id for row in held})
    for row in held:
        result.actions.append(end_position(person, row, spaces[row.workspace_id]))
    for workspace_id in sorted(grants, key=lambda key: spaces[key].name):
        result.actions.append(set_role(person, spaces[workspace_id], grants[workspace_id], None))
    if person.is_admin:
        result.actions.append(_admin(person))
    result.actions.append(set_status(person, "invited", today(settings)))
    result.actions.append(_credential(person, receipt, settings))
    places = last_placement(db, person)
    if places:
        message = (
            f"Before, {person.display_name} had: {', '.join(places)}. Nothing is given back automatically; "
            "use Transfer or Additional charge after review."
        )
        result.warnings.append(Warning("last_placement", message, str(person.id)))
    return result


def build(db: Session, request: Reinstate, actor_id: uuid.UUID, settings: Settings) -> Plan:
    """Invited status, no memberships or positions, a fresh activation code, last placement listed."""
    return draft(db, request, settings, {}).plan(request.kind, actor_id, request.model_dump(mode="json"))


def apply(
    db: Session, actor: User, plan: Plan, request: Reinstate, settings: Settings, reason: str
) -> tuple[User, dict]:
    receipt: dict = {}
    result = draft(db, request, settings, receipt)
    result.run(db, actor, reason)
    result.person.revision += 1
    db.flush()
    return result.person, receipt
