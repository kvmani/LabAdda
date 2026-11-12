"""Reviewed steps paired with the exact write that carries them out.

A kind's builder returns a ``Draft``: ordered actions, warnings, blockers and revisions. The plan
holds only the steps; apply rebuilds the same draft under lock (the digest proves it matches) and
runs each action in order, inside the caller's transaction.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date

from sqlalchemy.orm import Session

from .. import memberships, people, positions
from ..models import UnitPosition, User, Workspace
from ..security import revoke_user_sessions, utcnow
from .plan import Blocker, ChangeKind, Plan, Snapshot, Step, Warning

type Run = Callable[[Session, User, str], None]


@dataclass(frozen=True)
class Action:
    step: Step
    run: Run


@dataclass
class Draft:
    """Everything a kind computed from current state; ``extras`` feeds the receipt."""

    person: User
    actions: list[Action] = field(default_factory=list)
    warnings: list[Warning] = field(default_factory=list)
    blockers: list[Blocker] = field(default_factory=list)
    affected_people: int = 1

    def plan(self, kind: ChangeKind, actor_id: uuid.UUID, request: dict) -> Plan:
        return Plan(
            kind=kind,
            actor_id=str(actor_id),
            request=Snapshot(request),
            revisions=Snapshot({str(self.person.id): self.person.revision}),
            steps=tuple(action.step for action in self.actions),
            warnings=tuple(self.warnings),
            blockers=tuple(self.blockers),
            affected_people=self.affected_people,
        )

    def run(self, db: Session, actor: User, reason: str) -> None:
        for action in self.actions:
            action.run(db, actor, reason)
        db.flush()


def set_role(person: User, space: Workspace, before: str | None, after: str | None) -> Action:
    """Add, change or remove one direct membership through ``memberships``."""
    name = person.display_name
    if after is None:
        summary = f"Remove {name} from {space.name}"
    elif before is None:
        summary = f"Add {name} to {space.name} as {after}"
    else:
        summary = f"Set the role of {name} in {space.name} to {after}"

    def run(db: Session, actor: User, reason: str) -> None:
        if after is None:
            memberships.remove_membership(
                db, actor=actor, workspace_id=space.id, user_id=person.id, reason=reason
            )
        else:
            memberships.set_membership(
                db, actor=actor, workspace_id=space.id, user_id=person.id, role=after, reason=reason
            )

    return Action(
        Step("workspace", str(space.id), summary, Snapshot({"role": before}), Snapshot({"role": after})),
        run,
    )


def end_position(holder: User, row: UnitPosition, space: Workspace, *, revert: bool = False) -> Action:
    """End a current position; ``revert`` also returns the holder to the role recorded for it."""
    label = positions.title(row)
    returns = row.revert_role if revert else None
    summary = f"End the position of {holder.display_name} as {label} of {space.name}"
    if returns == "none":
        summary += " and remove the membership given for it"
    elif returns:
        summary += f" and return them to {returns}"

    def run(db: Session, actor: User, reason: str) -> None:
        current = db.get(UnitPosition, row.id)
        if current is None:
            return
        positions.end(db, current, actor=actor, reason=reason)
        if revert:
            positions.revert(db, current, actor=actor, reason=reason)

    return Action(
        Step(
            "identity",
            str(holder.id),
            summary,
            Snapshot({"position": label, "unit": space.name}),
            Snapshot({"position": None, "unit": space.name, "returns_to": returns}),
        ),
        run,
    )


@dataclass(frozen=True)
class Appointment:
    position: positions.PositionKind
    starts_on: date
    ends_on: date | None = None
    acting: bool = False
    revert_role: positions.RevertRole | None = None
    covers_id: uuid.UUID | None = None


def appoint(holder: User, space: Workspace, item: Appointment) -> Action:
    """Record a position; the membership step that makes the holder a steward comes first."""
    label = f"acting {positions.LABELS[item.position]}" if item.acting else positions.LABELS[item.position]
    summary = f"Appoint {holder.display_name} as {label} of {space.name}"
    if item.ends_on:
        summary += f" until {item.ends_on.isoformat()}"

    def run(db: Session, actor: User, reason: str) -> None:
        positions.appoint(
            db,
            actor=actor,
            workspace_id=space.id,
            user_id=holder.id,
            position=item.position,
            starts_on=item.starts_on,
            ends_on=item.ends_on,
            acting=item.acting,
            revert_role=item.revert_role,
            covers_id=item.covers_id,
            reason=reason,
        )

    after = {
        "position": label,
        "unit": space.name,
        "ends_on": item.ends_on.isoformat() if item.ends_on else None,
        "returns_to": item.revert_role,
    }
    return Action(
        Step("identity", str(holder.id), summary, Snapshot({"position": None}), Snapshot(after)),
        run,
    )


def set_status(
    person: User,
    status: people.StaffStatus,
    today: date,
    *,
    leave_sign_in: bool | None = None,
    expected_return_on: date | None = None,
) -> Action:
    """Change employment status; ending sign-in also ends every session at once."""
    enabled = status in {"invited", "active", "on_leave"} if leave_sign_in is None else leave_sign_in
    words = status.replace("_", " ")
    summary = f"Set the employment status of {person.display_name} to {words}"
    if person.is_active and not enabled:
        summary += " and end their sign-in and open sessions"
    before = {
        "status": person.status,
        "sign_in": person.is_active,
        "expected_return_on": person.expected_return_on.isoformat() if person.expected_return_on else None,
    }
    after = {
        "status": status,
        "sign_in": enabled,
        "expected_return_on": expected_return_on.isoformat() if expected_return_on else None,
    }

    def run(db: Session, actor: User, reason: str) -> None:
        was_active = person.is_active
        people.set_status(person, status, effective_on=today, leave_sign_in=leave_sign_in)
        person.expected_return_on = expected_return_on
        if was_active and not person.is_active:
            person.deactivated_at = utcnow()
            revoke_user_sessions(db, person.id)
        elif person.is_active:
            person.deactivated_at = None

    return Action(Step("identity", str(person.id), summary, Snapshot(before), Snapshot(after)), run)
