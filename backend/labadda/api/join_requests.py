"""Public organisation applications and serialized administrator review."""

import re
import uuid
from collections.abc import Iterator
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator
from sqlalchemy import func, select, text
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.orm import Session

from .. import audit, joining, memberships, people
from ..config import Settings
from ..credentials import issue_credential
from ..deps import Actor, current_actor, get_db, get_settings, origin_allowed, require_console
from ..errors import ApiError, Conflict, Forbidden, NotFound, TooMany
from ..models import JoinRequest, User, Workspace
from ..security import login_limiter, utcnow
from ..serialize import iso
from .todos import _actor, _scope_locks

USERNAME_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{1,62}$")
router = APIRouter(prefix="/join-requests", tags=["join-requests"])
admin_router = APIRouter(prefix="/admin/join-requests", tags=["admin join-requests"])
console_people = require_console("people", unit_admin=False)
type Reason = Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=500)]


def _bounded_db(db: Session = Depends(get_db)) -> Iterator[Session]:
    """Bound duplicate/review lock waits and report database unavailability without partial grants."""
    try:
        db.execute(text("SET LOCAL lock_timeout = '2s'"))
        db.execute(text("SET LOCAL statement_timeout = '2s'"))
        yield db
    except DBAPIError:
        db.rollback()
        raise ApiError(
            "applications_unavailable", "Applications are busy. Refresh and try again.", 503
        ) from None


class JoinRequestCreate(BaseModel):
    """Only affiliation claims are accepted, never roles or activation state."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    full_name: str = Field(min_length=2, max_length=120)
    username: str = Field(min_length=2, max_length=63)
    employee_no: str | None = Field(default=None, max_length=64)
    contact_email: str | None = Field(default=None, max_length=254)
    contact_phone: str | None = Field(default=None, max_length=64)
    designation: str | None = Field(default=None, max_length=120)
    unit_id: uuid.UUID | None = None
    custom_unit_name: str | None = Field(default=None, min_length=1, max_length=120)
    statement_of_interest: str | None = Field(default=None, max_length=2000)

    @field_validator("username", mode="before")
    @classmethod
    def normalize_username(cls, value: object) -> object:
        if isinstance(value, str):
            value = value.strip().lower()
            if not USERNAME_RE.fullmatch(value):
                raise ValueError("Use 2-63 lowercase letters, digits, dot, dash or underscore.")
        return value

    @field_validator("full_name", mode="before")
    @classmethod
    def normalize_name(cls, value: object) -> object:
        return " ".join(value.split()) if isinstance(value, str) else value


class RejectRequest(BaseModel):
    """A reason is retained with the terminal review decision."""

    model_config = ConfigDict(extra="forbid")
    reason: Reason | None = None


class ApproveRequest(BaseModel):
    """Corrections verified by an administrator, not authority supplied by the applicant."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    unit_id: uuid.UUID | None = None
    custom_unit_name: str | None = Field(default=None, min_length=1, max_length=120)
    employee_no: str | None = Field(default=None, max_length=64)
    designation: str | None = Field(default=None, max_length=120)
    full_name: str | None = Field(default=None, min_length=2, max_length=120)


@router.get("/units")
def available_units(
    search: str = Query(default="", max_length=120),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(_bounded_db),
) -> dict:
    """A bounded public affiliation catalogue never names private groups or projects."""
    rows = db.scalars(
        select(Workspace)
        .where(
            Workspace.kind == "org", Workspace.archived.is_(False), Workspace.name.ilike("%" + search + "%")
        )
        .order_by(Workspace.name, Workspace.id)
        .offset(offset)
        .limit(501)
    ).all()
    return {
        "units": [
            {"id": str(unit.id), "name": unit.name, "kind": unit.kind, "level": unit.level or "unit"}
            for unit in rows[:500]
        ],
        "has_more": len(rows) > 500,
    }


@router.post("")
def submit_join_request(
    body: JoinRequestCreate,
    request: Request,
    db: Session = Depends(_bounded_db),
    settings: Settings = Depends(get_settings),
) -> dict:
    """Accept a claim without exposing staff identities or conferring access."""
    if not origin_allowed(request.headers.get("origin"), request.headers.get("host"), settings):
        raise Forbidden("bad_origin", "Request origin is not trusted.")
    client = request.client.host if request.client else "unknown"
    if not login_limiter.hit(
        f"join:{client}", settings.login_attempts_per_window, settings.login_window_seconds
    ):
        raise TooMany()
    unit = joining.organisation_unit(db, body.unit_id) if body.unit_id else None
    request = JoinRequest(
        **body.model_dump(exclude={"custom_unit_name"}),
        unit_name=unit.name if unit else body.custom_unit_name,
        status="pending",
    )
    request.employee_no = request.employee_no or None
    db.add(request)
    db.commit()
    return {
        "id": str(request.id),
        "status": "pending",
        "message": "Thank you! An administrator will verify your application and issue an activation code.",
    }


def _request_to_dict(request: JoinRequest) -> dict:
    fields = (
        "full_name",
        "username",
        "employee_no",
        "contact_email",
        "contact_phone",
        "designation",
        "unit_name",
        "statement_of_interest",
        "status",
        "review_note",
    )
    result = {field: getattr(request, field) for field in fields}
    for field in ("id", "unit_id", "reviewed_by", "created_user_id"):
        value = getattr(request, field)
        result[field] = str(value) if value is not None else None
    return {**result, "created_at": iso(request.created_at), "reviewed_at": iso(request.reviewed_at)}


@admin_router.get("")
def list_join_requests(
    request: Request,
    *,
    status: Literal["all", "pending", "approved", "rejected"] = "pending",
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    actor: Actor = Depends(console_people),
    db: Session = Depends(_bounded_db),
) -> dict:
    """Review metadata is bounded and authority is refreshed just before delivery."""
    query = select(JoinRequest)
    if status != "all":
        query = query.where(JoinRequest.status == status)
    rows = db.scalars(
        query.order_by(JoinRequest.created_at.desc(), JoinRequest.id).offset(offset).limit(limit + 1)
    ).all()
    counts = dict(db.execute(select(JoinRequest.status, func.count()).group_by(JoinRequest.status)).all())
    items = [_request_to_dict(row) for row in rows[:limit]]
    db.expire_all()
    console_people(request, current_actor(request, db), db)
    return {
        "requests": items,
        "counts": {
            **{key: counts.get(key, 0) for key in ("pending", "approved", "rejected")},
            "total": sum(counts.values()),
        },
        "next_offset": offset + limit if len(rows) > limit else None,
    }


def _pending(db: Session, request_id: uuid.UUID) -> JoinRequest:
    db.execute(text("SET LOCAL lock_timeout = '2s'"))
    memberships.lock_admin_roles(db)
    request = db.get(JoinRequest, request_id, with_for_update=True, populate_existing=True)
    if request is None:
        raise NotFound()
    if request.status != "pending":
        raise Conflict("already_processed", "This application has already been reviewed. Refresh the list.")
    return request


def _authorize(request: Request, actor: Actor, db: Session) -> None:
    _actor(request, actor, db, True)
    console_people(request, actor, db)


@admin_router.post("/{request_id}/approve")
def approve_join_request(
    request_id: uuid.UUID,
    request: Request,
    *,
    body: ApproveRequest | None = None,
    actor: Actor = Depends(console_people),
    db: Session = Depends(_bounded_db),
    settings: Settings = Depends(get_settings),
) -> dict:
    """Create exactly one invited member and activation code after serialized verification."""
    pending = _pending(db, request_id)
    body = body or ApproveRequest()
    target, new_name = joining.target_plan(db, pending, body.unit_id, body.custom_unit_name)
    memberships.lock_workspace_roles(db, target.id)
    _scope_locks(db, target.id)
    _authorize(request, actor, db)
    target = joining.organisation_unit(db, target.id)
    full_name = body.full_name if body.full_name is not None else pending.full_name
    employee = body.employee_no if body.employee_no is not None else pending.employee_no
    employee = employee.strip() or None if employee else None
    designation = body.designation if body.designation is not None else pending.designation
    joining.check_identity(db, pending.username, employee)
    try:
        if new_name:
            target = joining.create_unit(db, target, new_name, actor.user)
        person = User(
            username=pending.username,
            display_name=full_name,
            employee_no=employee,
            designation=designation,
            contact_email=pending.contact_email,
            contact_phone=pending.contact_phone,
            is_admin=False,
            must_set_password=True,
            home_workspace_id=target.id,
            joined_on=people.site_date(settings),
        )
        people.set_status(person, "invited", effective_on=people.site_date(settings))
        db.add(person)
        db.flush()
        memberships.set_membership(
            db,
            actor=actor.user,
            workspace_id=target.id,
            user_id=person.id,
            role="member",
            reason="Verified voluntary application",
        )
        code, credential = issue_credential(db, person, "activation", actor.user, settings)
        _mark_approved(db, pending, person, target, actor)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise Conflict(
            "identity_conflict", "Staff records changed during review. Refresh and verify again."
        ) from None
    console_people(request, current_actor(request, db), db)
    return {
        "status": "approved",
        "activation": {"code": code, "expires_at": iso(credential.expires_at)},
        "user": {"id": str(person.id), "username": person.username, "display_name": person.display_name},
    }


def _mark_approved(db: Session, pending: JoinRequest, person: User, unit: Workspace, actor: Actor) -> None:
    pending.status = "approved"
    pending.reviewed_at = utcnow()
    pending.reviewed_by = actor.id
    pending.created_user_id = person.id
    pending.unit_id = unit.id
    pending.unit_name = unit.name
    pending.full_name = person.display_name
    pending.employee_no = person.employee_no
    pending.designation = person.designation
    audit.record(
        db,
        actor=actor.user,
        action="join_request.approved",
        scope_type="people",
        target_id=person.id,
        reason="Verified voluntary application",
        before="pending",
        after="approved",
    )


@admin_router.post("/{request_id}/reject")
def reject_join_request(
    request_id: uuid.UUID,
    request: Request,
    *,
    body: RejectRequest | None = None,
    actor: Actor = Depends(console_people),
    db: Session = Depends(_bounded_db),
) -> dict:
    """A rejected application cannot race an approval that already created an account."""
    pending = _pending(db, request_id)
    _authorize(request, actor, db)
    reason = body.reason if body and body.reason else "Application declined by administrator"
    pending.status = "rejected"
    pending.reviewed_at = utcnow()
    pending.reviewed_by = actor.id
    pending.review_note = reason
    audit.record(
        db,
        actor=actor.user,
        action="join_request.rejected",
        scope_type="people",
        target_id=pending.id,
        reason=reason,
        before="pending",
        after="rejected",
    )
    db.commit()
    return {"status": "rejected", "id": str(pending.id)}
