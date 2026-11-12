"""Bounded, cursor-paginated staff metadata; never reads collaboration content."""

import base64
import hashlib
import json
import uuid
from dataclasses import asdict, dataclass
from datetime import date
from typing import Literal

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from . import positions
from .errors import Invalid, NotFound
from .models import Membership, User, Workspace
from .people import StaffStatus

DirectorySort = Literal["name", "username", "employee_no", "status", "last_seen_on"]
DirectoryRole = Literal["admin", "member", "steward"]
SORTS = {
    "name": User.display_name,
    "username": User.username,
    "employee_no": User.employee_no,
    "status": User.status,
    "last_seen_on": User.last_seen_on,
}


@dataclass(frozen=True)
class DirectoryFilters:
    q: str = ""
    status: StaffStatus | None = None
    unit_id: uuid.UUID | None = None
    include_children: bool = True
    role: DirectoryRole | None = None
    sort: DirectorySort = "name"
    descending: bool = False


def _unit_ids(db: Session, filters: DirectoryFilters) -> set[uuid.UUID] | None:
    if filters.unit_id is None:
        return None
    parents = dict(db.execute(select(Workspace.id, Workspace.parent_id).where(Workspace.kind == "org")).all())
    if filters.unit_id not in parents:
        raise NotFound()
    selected = {filters.unit_id}
    if filters.include_children:
        pending = {filters.unit_id}
        while pending:
            pending = {child for child, parent in parents.items() if parent in pending} - selected
            selected.update(pending)
    return selected


def directory_query(db: Session, filters: DirectoryFilters):
    """Build staff/home-unit predicates without joining content or multiplying rows."""
    query = select(User, Workspace).outerjoin(
        Workspace, and_(Workspace.id == User.home_workspace_id, Workspace.kind == "org")
    )
    if filters.q.strip():
        pattern = filters.q.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        query = query.where(
            or_(
                *(
                    column.ilike("%" + pattern + "%", escape="\\")
                    for column in (User.display_name, User.username, User.employee_no)
                )
            )
        )
    if filters.status is not None:
        query = query.where(User.status == filters.status)
    units = _unit_ids(db, filters)
    if units is not None:
        query = query.where(User.home_workspace_id.in_(units))
    if filters.role == "admin":
        query = query.where(User.is_admin.is_(True))
    elif filters.role is not None:
        memberships = select(Membership.user_id).where(Membership.role == filters.role)
        if units is not None:
            memberships = memberships.where(Membership.workspace_id.in_(units))
        query = query.where(User.id.in_(memberships))
    column = SORTS[filters.sort]
    return query.order_by((column.desc() if filters.descending else column.asc()).nullslast(), User.id.asc())


def person_json(person: User, unit: Workspace | None) -> dict:
    """Publish an explicit directory allowlist, including only a date for sign-in."""
    return {
        "id": str(person.id),
        "username": person.username,
        "display_name": person.display_name,
        "employee_no": person.employee_no,
        "designation": person.designation,
        "status": person.status,
        "revision": person.revision,
        "is_admin": person.is_admin,
        "sign_in_enabled": person.is_active and not person.must_set_password,
        "home_unit": {"id": str(unit.id), "name": unit.name} if unit else None,
        "last_seen_on": person.last_seen_on.isoformat() if person.last_seen_on else None,
    }


def _fingerprint(filters: DirectoryFilters) -> str:
    payload = json.dumps(asdict(filters), sort_keys=True, default=str)
    return hashlib.sha256(payload.encode()).hexdigest()


def _decode(cursor: str, filters: DirectoryFilters) -> tuple[str | date | None, uuid.UUID]:
    try:
        payload = json.loads(
            base64.b64decode(cursor + "=" * (-len(cursor) % 4), altchars=b"-_", validate=True)
        )
        if not isinstance(payload, dict):
            raise ValueError
        if not isinstance(payload.get("id"), str):
            raise ValueError
        if set(payload) != {"fingerprint", "value", "id"} or payload["fingerprint"] != _fingerprint(filters):
            raise ValueError
        value = payload["value"]
        if value is not None and (not isinstance(value, str) or len(value) > 120):
            raise ValueError
        if value is not None and filters.sort == "last_seen_on":
            value = date.fromisoformat(value)
        return value, uuid.UUID(payload["id"])
    except (ValueError, TypeError, KeyError):
        raise Invalid("invalid_cursor", "Reload the directory after changing its filters.") from None


def directory_page(db: Session, filters: DirectoryFilters, limit: int, cursor: str | None) -> dict:
    """Read one stable page, keeping null sort values last in either direction."""
    query = directory_query(db, filters)
    column = SORTS[filters.sort]
    if cursor:
        value, identity = _decode(cursor, filters)
        if value is None:
            query = query.where(column.is_(None), User.id > identity)
        else:
            comparison = column < value if filters.descending else column > value
            query = query.where(or_(comparison, and_(column == value, User.id > identity), column.is_(None)))
    rows = db.execute(query.limit(limit + 1).execution_options(populate_existing=True)).all()
    page = rows[:limit]
    next_cursor = None
    if len(rows) > limit:
        person = page[-1][0]
        value = getattr(person, {"name": "display_name"}.get(filters.sort, filters.sort))
        payload = {
            "fingerprint": _fingerprint(filters),
            "value": value.isoformat() if isinstance(value, date) else value,
            "id": str(person.id),
        }
        next_cursor = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
    held = positions.positions_by_person(db, [person.id for person, _ in page])
    people = [{**person_json(person, unit), "positions": held.get(person.id, [])} for person, unit in page]
    return {"people": people, "next_cursor": next_cursor}
