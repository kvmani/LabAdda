"""Turn a parsed staff list into a dry-run report of ordinary, individually reviewable requests."""

import uuid
from hashlib import sha256

from pydantic import BaseModel, ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import policy
from ..config import Settings
from ..models import User, Workspace
from . import importer, service
from .plan import Plan, canonical_json
from .requests import AddPerson, EditPerson, NewStaffFields, StaffFields, Suspend, Transfer

ABSENT_LIMIT = 500
CURRENT = ("invited", "active", "on_leave")
GROUPS = ("add", "change", "transfer", "errors")


def _message(error: ValidationError) -> str:
    texts = {item["msg"].removeprefix("Value error, ") for item in error.errors()}
    return " ".join(sorted(texts)) if texts else "Check the values on this line."


class _Context:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.users = {user.username: user for user in db.scalars(select(User))}
        self.employees = {user.employee_no: user for user in self.users.values() if user.employee_no}
        self.units = {
            unit.code: unit
            for unit in db.scalars(
                select(Workspace).where(
                    Workspace.kind == "org", Workspace.archived.is_(False), Workspace.code.is_not(None)
                )
            )
        }


def _new_person(row: importer.Row, ctx: _Context) -> list:
    unit = ctx.units.get(row.unit_code or "")
    if not row.display_name:
        row.errors.append("A new person needs a display name.")
    if row.unit_code is None:
        row.errors.append("A new person needs a unit code.")
    elif unit is None:
        row.errors.append(f"No open unit has the code {row.unit_code}.")
    if row.status not in (None, "active", "invited"):
        row.errors.append("New people start as invited. Leave the status blank or use active.")
    if row.errors:
        return []
    try:
        fields = NewStaffFields(designation=row.designation, employee_no=row.employee_no)
        return [
            AddPerson(
                kind="add_person",
                username=row.username,
                display_name=row.display_name,
                fields=fields,
                home_unit_id=unit.id,
                role=row.role or "member",
                joined_on=row.effective_on,
            )
        ]
    except ValidationError as error:
        row.errors.append(_message(error))
        return []


def _existing(row: importer.Row, person: User, ctx: _Context) -> list:
    requests: list = []
    selected = {
        name: value
        for name in ("display_name", "designation", "employee_no")
        if (value := getattr(row, name)) is not None and value != getattr(person, name)
    }
    holder = ctx.employees.get(row.employee_no or "")
    if holder is not None and holder.id != person.id:
        row.errors.append("That employee number belongs to someone else.")
    if selected and not row.errors:
        try:
            requests.append(
                EditPerson(kind="edit_person", person_id=person.id, fields=StaffFields(**selected))
            )
        except ValidationError as error:
            row.errors.append(_message(error))
    unit = ctx.units.get(row.unit_code or "")
    if row.unit_code and unit is None:
        row.errors.append(f"No open unit has the code {row.unit_code}.")
    elif unit is not None and unit.id != person.home_workspace_id:
        requests.append(
            Transfer(kind="transfer", person_id=person.id, to_unit_id=unit.id, role=row.role or "member")
        )
    elif unit is not None and row.role and policy.direct_grants(ctx.db, person.id).get(unit.id) != row.role:
        row.warnings.append("The role differs from the current one. Change roles from the person's profile.")
    if row.status == "suspended" and person.status != "suspended":
        requests.append(Suspend(kind="suspend", person_id=person.id))
    elif row.status in ("retired", "left", "on_leave") and person.status != row.status:
        row.errors.append("Record leave, retirement or departure from the person's profile.")
    elif row.status in ("active", "invited") and person.status in ("suspended", "retired", "left"):
        row.warnings.append("Import does not give access back. Use the person's profile to reinstate them.")
    return requests


def _reviewed(
    row: importer.Row, requests: list, ctx: _Context, actor_id: uuid.UUID, settings: Settings
) -> list[str]:
    """Ask each request's own builder, so import warnings and blockers match the profile screens."""
    plans: list[Plan] = [service.build(ctx.db, item, actor_id, settings) for item in requests]
    for plan in plans:
        row.errors += [blocker.message for blocker in plan.blockers]
        row.warnings += [warning.message for warning in plan.warnings]
    return [step.summary for plan in plans for step in plan.steps if "activation code" not in step.summary]


def _group(requests: list) -> str:
    kinds = {item.kind for item in requests}
    if "add_person" in kinds:
        return "add"
    return "transfer" if "transfer" in kinds else "change"


def _entry(row: importer.Row, person: User | None, requests: list, summary: list[str]) -> dict:
    failed = bool(row.errors)
    return {
        "line": row.line,
        "group": "errors" if failed else _group(requests),
        "username": row.username,
        "display_name": row.display_name or (person.display_name if person else None),
        "summary": [] if failed else summary,
        "errors": row.errors,
        "warnings": row.warnings,
        "requests": [] if failed else [dump(item) for item in requests],
    }


def dump(item: BaseModel) -> dict:
    return item.model_dump(mode="json", exclude_unset=True)


def build(db: Session, data: bytes, actor_id: uuid.UUID, settings: Settings) -> dict:
    """Parse and review; nothing is written and the file itself is never kept."""
    parsed = importer.parse(data)
    ctx = _Context(db)
    rows, unchanged = [], 0
    for row in parsed:
        person = ctx.users.get(row.username)
        requests: list = []
        if not row.errors:
            requests = _new_person(row, ctx) if person is None else _existing(row, person, ctx)
        summary = _reviewed(row, requests, ctx, actor_id, settings) if requests and not row.errors else []
        if not row.errors and not requests:
            unchanged += 1
            continue
        rows.append(_entry(row, person, requests, summary))
    listed = {row.username for row in parsed}
    current = (user for user in ctx.users.values() if user.status in CURRENT and user.username not in listed)
    absent = sorted(current, key=lambda user: user.username)
    counts = {group: sum(1 for row in rows if row["group"] == group) for group in GROUPS}
    body = {"rows": rows, "counts": {**counts, "unchanged": unchanged}}
    return {
        **body,
        "absent": [{"username": u.username, "display_name": u.display_name} for u in absent[:ABSENT_LIMIT]],
        "absent_total": len(absent),
        "digest": sha256(canonical_json(body).encode("utf-8")).hexdigest(),
    }
