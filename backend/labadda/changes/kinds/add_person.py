"""Onboard an invited person with a home-unit membership and a one-time activation code."""

import difflib
import re
import uuid
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from ... import memberships, people
from ...config import Settings
from ...credentials import issue_credential
from ...errors import NotFound
from ...models import User, Workspace
from ...serialize import iso
from ..guards import unique_employee_number
from ..plan import Blocker, Plan, Snapshot, Step, Warning
from ..requests import AddPerson

SIMILAR_NAME_RATIO = 0.88
MAX_SIMILAR_WARNINGS = 5


def placeholder(username: str) -> str:
    """Name the not-yet-created account in plan steps; audits record the real identity."""
    return f"new:{username}"


def _name_key(name: str) -> str:
    words = re.sub(r"[^\w\s]", " ", name.casefold()).split()
    return " ".join(sorted(words))


def similar_names(db: Session, display_name: str) -> list[Warning]:
    """Warn about likely duplicates; the administrator decides, so this never blocks."""
    wanted = _name_key(display_name)
    rows = db.execute(select(User.id, User.display_name, User.username).order_by(User.username)).all()
    warnings = []
    for identity, name, username in rows:
        ratio = difflib.SequenceMatcher(None, wanted, _name_key(name)).ratio()
        if ratio >= SIMILAR_NAME_RATIO:
            message = f"{name} ({username}) has a very similar name. Check this is not the same person."
            warnings.append(Warning("similar_name", message, str(identity)))
    return warnings[:MAX_SIMILAR_WARNINGS]


def _unit_blockers(unit: Workspace) -> list[Blocker]:
    if unit.kind != "org" or unit.archived:
        return [Blocker("unit_unavailable", "Choose an open unit of the organisation as the home unit.")]
    return []


def _record(request: AddPerson, joined_on: str) -> dict:
    return {
        "username": request.username,
        "display_name": request.display_name,
        "status": "invited",
        **request.fields.model_dump(),
        "joined_on": joined_on,
    }


def build(db: Session, request: AddPerson, actor_id: uuid.UUID, settings: Settings) -> Plan:
    """Describe the new account, its home membership and its activation code without writing."""
    unit = db.get(Workspace, request.home_unit_id, populate_existing=True)
    if unit is None:
        raise NotFound()
    joined_on = (request.joined_on or people.site_date(settings)).isoformat()
    blockers = _unit_blockers(unit)
    if db.scalar(select(User.id).where(User.username == request.username)) is not None:
        blockers.append(Blocker("username_taken", "That username is already in use. Choose another."))
    blockers += unique_employee_number(db, request.fields.employee_no)
    target = placeholder(request.username)
    steps = (
        Step(
            "identity",
            target,
            f"Create an invited account for {request.display_name} ({request.username})",
            Snapshot({}),
            Snapshot(_record(request, joined_on)),
        ),
        Step(
            "workspace",
            str(unit.id),
            f"Make {unit.name} the home unit of {request.display_name}, as {request.role}",
            Snapshot({"role": None, "home": False}),
            Snapshot({"role": request.role, "home": True}),
        ),
        Step(
            "identity",
            target,
            "Issue a one-time activation code",
            Snapshot({"activation": None}),
            Snapshot({"activation": "issued"}),
        ),
    )
    return Plan(
        kind=request.kind,
        actor_id=str(actor_id),
        request=Snapshot(request.model_dump(mode="json")),
        revisions=Snapshot({}),
        steps=steps,
        warnings=tuple(similar_names(db, request.display_name)),
        blockers=tuple(blockers),
        affected_people=1,
    )


def apply(
    db: Session, actor: User, plan: Plan, request: AddPerson, settings: Settings, reason: str
) -> tuple[User, dict]:
    """Create the account, membership and code from the rebuilt plan in the caller's transaction."""
    record = plan.steps[0].after.to_dict()
    person = User(
        username=request.username,
        display_name=request.display_name,
        is_admin=False,
        must_set_password=True,
        designation=request.fields.designation,
        employee_no=request.fields.employee_no,
        contact_email=request.fields.contact_email,
        contact_phone=request.fields.contact_phone,
        joined_on=date.fromisoformat(str(record["joined_on"])),
        home_workspace_id=request.home_unit_id,
    )
    people.set_status(person, "invited", effective_on=people.site_date(settings))
    db.add(person)
    db.flush()
    memberships.set_membership(
        db,
        actor=actor,
        workspace_id=request.home_unit_id,
        user_id=person.id,
        role=request.role,
        reason=reason,
    )
    code, credential = issue_credential(db, person, "activation", actor, settings)
    db.flush()
    return person, {"activation": {"code": code, "expires_at": iso(credential.expires_at)}}
