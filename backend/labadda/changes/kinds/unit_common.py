"""Drafts, checks and access counts shared by the organisation-unit change kinds (PO-19)."""

import uuid
from collections import Counter
from dataclasses import dataclass, field

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ... import memberships, policy
from ...models import Membership, User, Workspace
from ..actions import Action
from ..plan import Blocker, ChangeKind, Plan, Snapshot, Step, Warning
from .common import named

MAX_MOVED_PEOPLE = 500
MOVABLE = {"invited", "active", "on_leave"}


@dataclass
class UnitDraft:
    """What a unit change computed from current state; plans carry only the steps."""

    unit: Workspace
    actions: list[Action] = field(default_factory=list)
    warnings: list[Warning] = field(default_factory=list)
    blockers: list[Blocker] = field(default_factory=list)
    affected_people: int = 0
    box: dict = field(default_factory=dict)  # holds what a step creates, for later steps

    def plan(self, kind: ChangeKind, actor_id: uuid.UUID, request: dict) -> Plan:
        # Units carry no revision counter; the digest over their before/after state is the guard.
        return Plan(
            kind=kind,
            actor_id=str(actor_id),
            request=Snapshot(request),
            revisions=Snapshot({}),
            steps=tuple(action.step for action in self.actions),
            warnings=tuple(self.warnings),
            blockers=tuple(self.blockers),
            affected_people=self.affected_people,
        )

    def run(self, db: Session, actor: User, reason: str) -> None:
        for action in self.actions:
            action.run(db, actor, reason)
        db.flush()


def lock_units(db: Session, unit_ids: set[uuid.UUID]) -> None:
    """Role locks in a fixed order, as every membership writer takes them."""
    for unit_id in sorted(unit_ids, key=str):
        memberships.lock_workspace_roles(db, unit_id)


def org_parents(db: Session) -> dict[uuid.UUID, uuid.UUID | None]:
    return dict(db.execute(select(Workspace.id, Workspace.parent_id).where(Workspace.kind == "org")).all())


def branch(parents: dict[uuid.UUID, uuid.UUID | None], unit_id: uuid.UUID) -> set[uuid.UUID]:
    """The unit and every unit below it, from a parent map."""
    return {unit for unit in parents if unit == unit_id or unit_id in policy.ancestors(parents, unit)}


def unit_state(unit: Workspace, parent: Workspace | None) -> dict:
    return {
        "name": unit.name,
        "code": unit.code,
        "parent": parent.name if parent else None,
        "parent_id": str(unit.parent_id) if unit.parent_id else None,
        "archived": unit.archived,
    }


def code_taken(db: Session, code: str, unit_id: uuid.UUID | None = None) -> list[Blocker]:
    """Codes are unique among units, archived ones included, because imports resolve by code."""
    query = select(Workspace.id).where(Workspace.kind == "org", Workspace.code == code)
    if unit_id is not None:
        query = query.where(Workspace.id != unit_id)
    if db.scalar(query.limit(1)) is None:
        return []
    return [Blocker("duplicate_code", f"The code {code} is already used by another unit.")]


def open_unit(unit: Workspace | None, what: str = "unit") -> list[Blocker]:
    if unit is None or unit.kind != "org" or unit.archived:
        return [Blocker("unit_unavailable", f"Choose an open {what} of the organisation.")]
    return []


def org_unit(unit: Workspace) -> list[Blocker]:
    if unit.kind != "org":
        return [Blocker("unit_unavailable", "Only units of the organisation can be changed here.")]
    return []


def root_fixed(unit: Workspace, verb: str) -> list[Blocker]:
    if unit.parent_id is None and unit.kind == "org":
        return [Blocker("root_fixed", f"The top of the organisation cannot be {verb}.")]
    return []


def readable(grants: dict[uuid.UUID, str], parents: dict[uuid.UUID, uuid.UUID | None]) -> set[uuid.UUID]:
    reads = set(grants)
    for unit in grants:
        if unit in parents:
            reads.update(policy.ancestors(parents, unit))
    return reads


def access_counts(
    db: Session,
    scope: set[uuid.UUID],
    new_parents: dict[uuid.UUID, uuid.UUID | None],
    added: dict[uuid.UUID, set[uuid.UUID]] | None = None,
) -> list[Warning]:
    """People who gain or lose read access to units when ``scope`` units get new parents (and,
    for ``added``, new memberships). Only counts and unit names leave this function."""
    before_parents = org_parents(db)
    added = added or {}
    holders = set(
        db.scalars(
            select(Membership.user_id)
            .join(User, User.id == Membership.user_id)
            .where(Membership.workspace_id.in_(scope), User.is_active.is_(True))
        )
    ) | set(added)
    grants: dict[uuid.UUID, dict[uuid.UUID, str]] = {person: {} for person in holders}
    for person, unit, role in db.execute(
        select(Membership.user_id, Membership.workspace_id, Membership.role).where(
            Membership.user_id.in_(holders)
        )
    ):
        grants[person][unit] = role
    gained: Counter[uuid.UUID] = Counter()
    lost: Counter[uuid.UUID] = Counter()
    for person, direct in grants.items():
        after_grants = {**direct, **dict.fromkeys(added.get(person, ()), "member")}
        before = readable(direct, before_parents)
        after = readable(after_grants, new_parents)
        gained.update(after - before)
        lost.update(before - after)
    names = named(db, set(gained) | set(lost))
    warnings = []
    for code, counter, words in (
        ("access_gained", gained, "will be able to read"),
        ("access_lost", lost, "will no longer be able to read"),
    ):
        for unit in sorted(counter, key=lambda key: names[key].name):
            noun = "person" if counter[unit] == 1 else "people"
            message = f"{counter[unit]} {noun} {words} {names[unit].name}."
            warnings.append(Warning(code, message, str(unit), counter[unit]))
    return warnings


def people_with_home(db: Session, unit_id: uuid.UUID, *, for_update: bool = False) -> list[User]:
    query = select(User).where(User.home_workspace_id == unit_id).order_by(User.display_name, User.id)
    if for_update:
        query = query.with_for_update().execution_options(populate_existing=True)
    return list(db.scalars(query))


def person_count(db: Session, unit_id: uuid.UUID) -> int:
    return db.scalar(select(func.count()).select_from(User).where(User.home_workspace_id == unit_id)) or 0


def home_step(person: User, source: Workspace, target: Workspace, summary: str | None = None) -> Step:
    return Step(
        "identity",
        str(person.id),
        summary or f"Change the home unit of {person.display_name} to {target.name}",
        Snapshot({"home_unit_id": str(source.id), "home_unit": source.name}),
        Snapshot({"home_unit_id": str(target.id), "home_unit": target.name}),
    )


def set_home(person: User, unit_id: uuid.UUID, step: Step) -> Action:
    def run(db: Session, actor: User, reason: str) -> None:
        person.home_workspace_id = unit_id
        person.revision += 1

    return Action(step, run)


def create_action(name: str, code: str, parent: Workspace, box: dict, level: str | None = None) -> Action:
    """Create a unit; later steps of the same plan reach it through ``box``."""

    def run(db: Session, actor: User, reason: str) -> None:
        unit = Workspace(
            kind="org", name=name, code=code, level=level, parent_id=parent.id, created_by=actor.id
        )
        db.add(unit)
        db.flush()
        box["unit"] = unit

    before = Snapshot({"name": None, "code": None, "parent": None, "archived": None})
    after = Snapshot({"name": name, "code": code, "parent": parent.name, "archived": False})
    summary = f"Create the {level or 'unit'} {name} ({code}) under {parent.name}"
    return Action(Step("workspace", "new:unit", summary, before, after), run)


def join_new_action(person: User, unit_name: str, role: str, box: dict) -> Action:
    def run(db: Session, actor: User, reason: str) -> None:
        memberships.set_membership(
            db, actor=actor, workspace_id=box["unit"].id, user_id=person.id, role=role, reason=reason
        )

    step = Step(
        "workspace",
        "new:unit",
        f"Add {person.display_name} to {unit_name} as {role}",
        Snapshot({"role": None}),
        Snapshot({"role": role}),
    )
    return Action(step, run)


def home_in_new_action(person: User, source: Workspace, unit_name: str, box: dict) -> Action:
    def run(db: Session, actor: User, reason: str) -> None:
        person.home_workspace_id = box["unit"].id
        person.revision += 1

    step = Step(
        "identity",
        str(person.id),
        f"Change the home unit of {person.display_name} to {unit_name}",
        Snapshot({"home_unit_id": str(source.id), "home_unit": source.name}),
        Snapshot({"home_unit_id": "new:unit", "home_unit": unit_name}),
    )
    return Action(step, run)
