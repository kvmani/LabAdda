"""Spreadsheet import: one new account in its unit, with an activation code or a first password."""

import uuid
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from ... import memberships, people
from ...config import Settings
from ...credentials import issue_credential
from ...errors import Invalid
from ...models import User
from ...security import MIN_PASSWORD_LENGTH, hash_password
from ...serialize import iso
from .. import import_tree
from ..guards import unique_employee_number
from ..import_requests import ImportPerson
from ..plan import Blocker, Plan, Snapshot, Step
from . import add_person, import_unit

lock_scope = import_unit.lock_scope


def _record(request: ImportPerson, joined_on: str) -> dict:
    return {
        "username": request.username,
        "display_name": request.display_name,
        "status": "invited" if request.active and not request.has_password else None,
        "employee_no": request.employee_no,
        "contact_email": request.email,
        "extension": request.extension,
        "residence_phone": request.residence_phone,
        "joined_on": joined_on,
    }


def _blockers(db: Session, request: ImportPerson, found: import_tree.Found) -> list[Blocker]:
    blockers = list(found.blockers)
    if db.scalar(select(User.id).where(User.username == request.username)) is not None:
        blockers.append(Blocker("username_taken", "That username is already in use. Choose another."))
    blockers += unique_employee_number(db, request.employee_no)
    if request.site_role == "admin" and not request.active:
        blockers.append(Blocker("admin_inactive", "A site administrator must be active."))
    if request.password is not None and len(request.password.get_secret_value()) < MIN_PASSWORD_LENGTH:
        blockers.append(
            Blocker("weak_password", f"The password needs at least {MIN_PASSWORD_LENGTH} characters.")
        )
    return blockers


def _steps(request: ImportPerson, joined_on: str, place: str) -> tuple[Step, ...]:
    name = request.display_name
    target = add_person.placeholder(request.username)
    record = _record(request, joined_on)
    record["status"] = "suspended" if not request.active else "active" if request.has_password else "invited"
    steps = [
        Step(
            "identity",
            target,
            f"Create an account for {name} ({request.username})",
            Snapshot({}),
            Snapshot(record),
        ),
        Step(
            "identity",
            target,
            f"Make {place} the home unit of {name}, as member",
            Snapshot({"role": None, "home": False}),
            Snapshot({"role": "member", "home": True}),
        ),
    ]
    if request.site_role == "admin":
        steps.append(
            Step(
                "identity",
                target,
                f"Make {name} a site administrator",
                Snapshot({"is_admin": False}),
                Snapshot({"is_admin": True}),
            )
        )
    if request.has_password:
        steps.append(
            Step(
                "identity",
                target,
                f"Set the first password for {name}; they must change it when they first sign in",
                Snapshot({"password": None}),
                Snapshot({"password": "set", "must_change": True}),
            )
        )
    elif request.active:
        steps.append(
            Step(
                "identity",
                target,
                "Issue a one-time activation code",
                Snapshot({"activation": None}),
                Snapshot({"activation": "issued"}),
            )
        )
    return tuple(steps)


def build(db: Session, request: ImportPerson, actor_id: uuid.UUID, settings: Settings) -> Plan:
    found = import_tree.find(db, request.path)
    joined_on = people.site_date(settings).isoformat()
    place = " > ".join(node.name for node in request.path)
    return Plan(
        kind="add_person",
        actor_id=str(actor_id),
        request=Snapshot(request.model_dump(mode="json")),
        revisions=Snapshot({}),
        steps=_steps(request, joined_on, place),
        blockers=tuple(_blockers(db, request, found)),
        affected_people=1,
    )


def apply(
    db: Session, actor: User, plan: Plan, request: ImportPerson, settings: Settings, reason: str
) -> tuple[User, dict]:
    found = import_tree.find(db, request.path)
    home = found.home
    if home is None or found.blockers:
        raise Invalid("plan_blocked", "Resolve the blocking problems before applying this change.")
    today = people.site_date(settings)
    person = User(
        username=request.username,
        display_name=request.display_name,
        is_admin=request.site_role == "admin",
        must_set_password=not request.has_password,
        employee_no=request.employee_no,
        contact_email=request.email,
        extension=request.extension,
        residence_phone=request.residence_phone,
        joined_on=date.fromisoformat(str(plan.steps[0].after.to_dict()["joined_on"])),
        home_workspace_id=home.id,
    )
    status = "suspended" if not request.active else "active" if request.has_password else "invited"
    people.set_status(person, status, effective_on=today)
    if request.has_password:
        person.must_set_password = False
        person.must_change_password = True
        # Preview runs without the secret; only the real apply hashes it.
        if request.password is not None:
            person.password_hash = hash_password(request.password.get_secret_value())
    db.add(person)
    db.flush()
    memberships.set_membership(
        db, actor=actor, workspace_id=home.id, user_id=person.id, role="member", reason=reason
    )
    if request.has_password or not request.active:
        return person, {}
    code, credential = issue_credential(db, person, "activation", actor, settings)
    db.flush()
    return person, {"activation": {"code": code, "expires_at": iso(credential.expires_at)}}
