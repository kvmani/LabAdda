"""PO-24: hold a unit administrator's changes to their own branch.

Reach is read from the grants that exist now, inside the change protocol's locks, and never from
anything the client sends. A site administrator has no limit. A unit administrator may act on
people whose home is in their units, on those units and the units below, and nowhere else:

* a person or unit outside the branch answers with the uniform 404;
* a person who is a site administrator, or administers more than this actor, is refused with 403;
* a plan that would also touch anything outside the branch is blocked, and its text for those
  parts is replaced, so a review never names units the actor cannot see.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, replace

from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import policy, positions
from ..errors import Forbidden, NotFound
from ..models import User, Workspace
from .plan import Blocker, Plan, Snapshot, Step

ADMIN_ONLY = ("unit_admin_grant", "unit_admin_revoke")
# Request fields that name one person or one unit, checked before anything is read or built.
PERSON_FIELDS = ("person_id", "successor_id", "replace_person_id", "head_id")
UNIT_FIELDS = ("home_unit_id", "to_unit_id", "workspace_id", "parent_id", "new_parent_id", "into_unit_id")
# The unit a structural change is about: it must lie below an administered unit, so the change
# cannot reveal or alter what sits above the branch.
INSIDE_FIELDS = ("unit_id",)
# Lists that point at workspaces the person already belongs to; every step they cause is checked
# after the plan is built, so a project or group outside the branch blocks the plan instead.
STEP_CHECKED = ("leave_workspace_ids", "keep_workspace_ids", "successors", "acting")
# These end every position the person holds, in any unit.
ENDS_POSITIONS = ("retire", "leave", "return", "suspend", "reinstate")

OUTSIDE = (
    "This change also reaches people, units or groups outside your units. A site administrator must make it."
)
HIDDEN = "This concerns a unit or group outside your units."
SELF_ACCESS = "Ask another administrator to give you access to a unit; an administrator cannot do it alone."
EARLIER_PLACES = "Nothing is given back automatically; use Transfer or Additional charge after review."


@dataclass(frozen=True)
class Reach:
    """What one unit administrator may act on, as read under the current locks."""

    actor: User
    units: frozenset[uuid.UUID]
    parents: dict[uuid.UUID, uuid.UUID | None]

    def person(self, db: Session, person_id: uuid.UUID) -> User:
        """A visible person this actor may change: home in the branch, and no larger authority."""
        person = db.get(User, person_id, populate_existing=True)
        if person is None or person.is_admin or person.home_workspace_id not in self.units:
            raise NotFound()
        if person.id != self.actor.id and not policy.people_scope(db, person) <= self.units:
            raise Forbidden("outside_your_units", "Only a site administrator can change this person.")
        return person

    def unit(self, unit_id: uuid.UUID, *, inside: bool = False) -> None:
        if unit_id not in self.units or (inside and self.parents.get(unit_id) not in self.units):
            raise NotFound()

    def check(self, db: Session, request) -> None:
        """Refuse a request that names anything outside the branch before it is built."""
        if request.kind in ADMIN_ONLY:
            raise Forbidden("admin_required", "Only a site administrator can appoint unit administrators.")
        for name in PERSON_FIELDS:
            if getattr(request, name, None) is not None:
                self.person(db, getattr(request, name))
        for person_id in getattr(request, "person_ids", ()):
            self.person(db, person_id)
        for name in UNIT_FIELDS:
            if getattr(request, name, None) is not None:
                self.unit(getattr(request, name))
        for name in INSIDE_FIELDS:
            if getattr(request, name, None) is not None:
                self.unit(getattr(request, name), inside=True)

    def plainly_inside(self, db: Session, request) -> bool:
        """True when the request passes and points at nothing that only a built plan could judge."""
        try:
            self.check(db, request)
        except (NotFound, Forbidden):
            return False
        return not any(getattr(request, name, None) for name in STEP_CHECKED)

    def _step_inside(self, db: Session, step: Step) -> bool:
        if step.target_id.startswith("new:"):
            return True
        target = uuid.UUID(step.target_id)
        if step.target_type == "workspace":
            return target in self.units
        person = db.get(User, target)
        return person is not None and not person.is_admin and person.home_workspace_id in self.units

    def _outside_positions(self, db: Session, request) -> bool:
        person_id = getattr(request, "person_id", None)
        if request.kind not in ENDS_POSITIONS or person_id is None:
            return False
        return any(row.workspace_id not in self.units for row in positions.current(db, user_id=person_id))

    def _gives_actor_access(self, request) -> bool:
        """A role or membership for the administrator themself would be content access by appointment."""
        me = self.actor.id
        if request.kind in ("additional_charge", "transfer"):
            return request.person_id == me
        if request.kind == "promote":
            return request.person_id == me and request.role is not None
        if request.kind == "change_authority":
            return request.successor_id == me
        covers = [*getattr(request, "successors", ()), *getattr(request, "acting", ())]
        return any(item.successor_id == me for item in covers)

    def _warnings(self, db: Session, warnings: tuple) -> tuple:
        """Warnings that name a person or the places they once held would show what lies outside."""
        kept = []
        for item in warnings:
            if item.code == "similar_name" and not self._sees_person(db, item.target_id):
                continue
            kept.append(replace(item, message=EARLIER_PLACES) if item.code == "last_placement" else item)
        return tuple(kept)

    def _sees_person(self, db: Session, person_id: str | None) -> bool:
        person = db.get(User, uuid.UUID(person_id)) if _is_uuid(person_id) else None
        return person is not None and not person.is_admin and person.home_workspace_id in self.units

    def restrict(self, db: Session, request, plan: Plan) -> Plan:
        """Block what leaves the branch and hide what the actor may not see; the digest follows."""
        steps = tuple(step if self._step_inside(db, step) else _hidden(step) for step in plan.steps)
        outside = any(new is not old for new, old in zip(steps, plan.steps, strict=True))
        if self._outside_positions(db, request):
            # Position steps carry a unit name but no unit id, so all of them are hidden.
            steps = tuple(_hidden(step) if _is_position(step) else step for step in steps)
            outside = True
        notes = [*plan.blockers, *plan.warnings]
        named = {uuid.UUID(note.target_id) for note in notes if _is_uuid(note.target_id)}
        spaces = set(db.scalars(select(Workspace.id).where(Workspace.id.in_(named)))) if named else set()
        hidden = {str(space) for space in spaces - self.units}
        blockers = tuple(
            replace(item, message=HIDDEN) if item.target_id in hidden else item for item in plan.blockers
        )
        warnings = tuple(
            replace(item, message=HIDDEN) if item.target_id in hidden else item for item in plan.warnings
        )
        warnings = self._warnings(db, warnings)
        if outside:
            blockers += (Blocker("outside_your_units", OUTSIDE),)
        if self._gives_actor_access(request):
            blockers += (Blocker("self_access", SELF_ACCESS),)
        return replace(plan, steps=steps, blockers=blockers, warnings=warnings)


def _is_position(step: Step) -> bool:
    return "position" in step.before.to_dict() or "position" in step.after.to_dict()


def _is_uuid(value: str | None) -> bool:
    try:
        uuid.UUID(value or "")
    except ValueError:
        return False
    return True


def _hidden(step: Step) -> Step:
    return Step(step.target_type, step.target_id, HIDDEN, Snapshot({}), Snapshot({}))


def reach_for(db: Session, user: User) -> Reach | None:
    """``None`` for a site administrator; otherwise the unit administrator's current reach."""
    if user.is_admin and user.is_active:
        return None
    units = policy.people_scope(db, user)
    if not units:
        raise Forbidden("admin_required", "Administrator access is required.")
    parents = dict(db.execute(select(Workspace.id, Workspace.parent_id).where(Workspace.kind == "org")).all())
    return Reach(user, units, parents)
