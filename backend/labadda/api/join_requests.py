"""Voluntary membership application and administrator approval endpoints."""

import re
import uuid
from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import audit, memberships, people
from ..config import Settings
from ..credentials import issue_credential
from ..deps import Actor, get_db, get_settings, require_console
from ..errors import Conflict, Invalid, NotFound
from ..models import JoinRequest, User, Workspace
from ..security import utcnow
from ..serialize import iso

USERNAME_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{1,62}$")

router = APIRouter(prefix="/join-requests", tags=["join-requests"])
admin_router = APIRouter(prefix="/admin/join-requests", tags=["admin join-requests"])
console_people = require_console("people", unit_admin=False)

type Reason = Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=500)]


class JoinRequestCreate(BaseModel):
    """Payload for submitting a voluntary membership application."""

    model_config = ConfigDict(extra="forbid")
    full_name: str = Field(min_length=2, max_length=120)
    username: str = Field(min_length=2, max_length=63)
    employee_no: str | None = Field(default=None, max_length=64)
    contact_email: str | None = Field(default=None, max_length=254)
    contact_phone: str | None = Field(default=None, max_length=64)
    designation: str | None = Field(default=None, max_length=120)
    unit_id: uuid.UUID | None = Field(default=None)
    custom_unit_name: str | None = Field(default=None, max_length=120)
    statement_of_interest: str | None = Field(default=None, max_length=2000)

    @field_validator("username", mode="before")
    @classmethod
    def normalize_username(cls, value: object) -> object:
        if isinstance(value, str):
            value = value.strip().lower()
            if not USERNAME_RE.match(value):
                raise ValueError("Use 2-63 lowercase letters, digits, dot, dash or underscore.")
        return value

    @field_validator("full_name", mode="before")
    @classmethod
    def normalize_name(cls, value: object) -> object:
        if isinstance(value, str):
            value = " ".join(value.strip().split())
            if not value:
                raise ValueError("Full name cannot be blank.")
        return value


class RejectRequest(BaseModel):
    """Payload for rejecting a join application."""

    model_config = ConfigDict(extra="forbid")
    reason: Reason | None = Field(default=None)


class ApproveRequest(BaseModel):
    """Optional modifications by administrator upon verification against official records."""

    model_config = ConfigDict(extra="forbid")
    unit_id: uuid.UUID | None = None
    custom_unit_name: str | None = Field(default=None, max_length=120)
    employee_no: str | None = Field(default=None, max_length=64)
    designation: str | None = Field(default=None, max_length=120)
    full_name: str | None = Field(default=None, max_length=120)


@router.get("/units")
def available_units(db: Session = Depends(get_db)) -> dict:
    """Return active laboratory organisation units and groups so applicants can select their affiliation."""
    rows = db.scalars(
        select(Workspace)
        .where(Workspace.kind.in_(["org", "group"]), Workspace.archived.is_(False))
        .order_by(Workspace.kind, Workspace.name)
    ).all()
    units = [
        {
            "id": str(w.id),
            "name": w.name,
            "kind": w.kind,
            "level": w.level or ("group" if w.kind == "group" else "unit"),
        }
        for w in rows
    ]
    return {"units": units}


@router.post("")
def submit_join_request(
    body: JoinRequestCreate,
    db: Session = Depends(get_db),
) -> dict:
    """Accept and record a voluntary application to join LabAdda."""
    existing_user = db.scalar(select(User.id).where(User.username == body.username))
    if existing_user is not None:
        raise Conflict(
            code="username_taken",
            message="That username is already in use by a registered user. Please choose another.",
        )

    pending_req = db.scalar(
        select(JoinRequest.id).where(
            JoinRequest.username == body.username,
            JoinRequest.status == "pending",
        )
    )
    if pending_req is not None:
        raise Conflict(
            code="already_applied",
            message="An application with this username is already pending administrator review.",
        )

    if body.employee_no:
        norm_emp = body.employee_no.strip()
        existing_emp = db.scalar(
            select(User.id).where(func.lower(User.employee_no) == func.lower(norm_emp))
        )
        if existing_emp is not None:
            raise Conflict(
                code="employee_no_taken",
                message="A staff record with this employee number already exists.",
            )

    unit_name = None
    if body.unit_id:
        target_unit = db.get(Workspace, body.unit_id)
        if target_unit and not target_unit.archived:
            unit_name = target_unit.name
        else:
            raise Invalid(code="invalid_unit", message="Selected unit is not valid or has been closed.")
    elif body.custom_unit_name and body.custom_unit_name.strip():
        unit_name = body.custom_unit_name.strip()

    req = JoinRequest(
        full_name=body.full_name,
        username=body.username,
        employee_no=body.employee_no.strip() if body.employee_no else None,
        contact_email=body.contact_email.strip() if body.contact_email else None,
        contact_phone=body.contact_phone.strip() if body.contact_phone else None,
        designation=body.designation.strip() if body.designation else None,
        unit_id=body.unit_id,
        unit_name=unit_name,
        statement_of_interest=body.statement_of_interest.strip() if body.statement_of_interest else None,
        status="pending",
    )
    db.add(req)
    db.commit()
    db.refresh(req)

    return {
        "id": str(req.id),
        "status": "pending",
        "message": (
            "Thank you! Your voluntary application to join LabAdda has been received. "
            "An administrator will review your profile and issue your activation credentials."
        ),
    }


def _request_to_dict(r: JoinRequest) -> dict:
    return {
        "id": str(r.id),
        "created_at": iso(r.created_at),
        "full_name": r.full_name,
        "username": r.username,
        "employee_no": r.employee_no,
        "contact_email": r.contact_email,
        "contact_phone": r.contact_phone,
        "designation": r.designation,
        "unit_id": str(r.unit_id) if r.unit_id else None,
        "unit_name": r.unit_name,
        "statement_of_interest": r.statement_of_interest,
        "status": r.status,
        "reviewed_at": iso(r.reviewed_at) if r.reviewed_at else None,
        "reviewed_by": str(r.reviewed_by) if r.reviewed_by else None,
        "review_note": r.review_note,
        "created_user_id": str(r.created_user_id) if r.created_user_id else None,
    }


@admin_router.get("")
def list_join_requests(
    status: Literal["all", "pending", "approved", "rejected"] = Query(default="pending"),
    limit: int = Query(default=50, ge=1, le=100),
    actor: Actor = Depends(console_people),
    db: Session = Depends(get_db),
) -> dict:
    """List voluntary join requests for administrator verification."""
    query = select(JoinRequest)
    if status != "all":
        query = query.where(JoinRequest.status == status)
    query = query.order_by(JoinRequest.created_at.desc()).limit(limit)

    requests = db.scalars(query).all()

    counts = {
        "pending": db.scalar(
            select(func.count(JoinRequest.id)).where(JoinRequest.status == "pending")
        )
        or 0,
        "approved": db.scalar(
            select(func.count(JoinRequest.id)).where(JoinRequest.status == "approved")
        )
        or 0,
        "rejected": db.scalar(
            select(func.count(JoinRequest.id)).where(JoinRequest.status == "rejected")
        )
        or 0,
        "total": db.scalar(select(func.count(JoinRequest.id))) or 0,
    }

    return {
        "requests": [_request_to_dict(r) for r in requests],
        "counts": counts,
    }


def _resolve_target_unit(
    db: Session, actor: Actor, req: JoinRequest, body: ApproveRequest | None
) -> tuple[uuid.UUID, str]:
    """Determine target workspace for the approved applicant, creating a new unit if needed."""
    chosen_id = body.unit_id if body and body.unit_id else None
    if chosen_id:
        ws = db.get(Workspace, chosen_id)
        if not ws or ws.archived:
            raise Invalid(code="invalid_unit", message="Selected unit does not exist or is archived.")
        return ws.id, ws.name

    custom_name = body.custom_unit_name if body and body.custom_unit_name else None
    if not custom_name and not req.unit_id and req.unit_name:
        custom_name = req.unit_name

    if custom_name and custom_name.strip():
        clean_name = custom_name.strip()
        existing = db.scalar(
            select(Workspace).where(
                Workspace.kind.in_(["org", "group"]),
                func.lower(Workspace.name) == func.lower(clean_name),
            )
        )
        if existing:
            return existing.id, existing.name

        root = db.scalar(
            select(Workspace).where(Workspace.kind == "org", Workspace.parent_id.is_(None))
        )
        new_ws = Workspace(
            kind="org",
            name=clean_name,
            parent_id=root.id if root else None,
            created_by=actor.user.id,
        )
        db.add(new_ws)
        db.flush()
        audit.record(
            db,
            actor=actor.user,
            action="tree.create",
            scope_type="workspace",
            scope_id=new_ws.id,
            kind="org",
            parent=root.id if root else None,
        )
        return new_ws.id, new_ws.name

    if req.unit_id:
        ws = db.get(Workspace, req.unit_id)
        if ws and not ws.archived:
            return ws.id, ws.name

    root_unit = db.scalar(
        select(Workspace).where(Workspace.kind == "org", Workspace.parent_id.is_(None))
    )
    if not root_unit:
        raise NotFound()
    return root_unit.id, root_unit.name


@admin_router.post("/{request_id}/approve")
def approve_join_request(
    request_id: uuid.UUID,
    body: ApproveRequest | None = None,
    actor: Actor = Depends(console_people),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> dict:
    """Approve a voluntary application, create an invited staff account and return activation code."""
    req = db.get(JoinRequest, request_id)
    if req is None:
        raise NotFound()
    if req.status != "pending":
        raise Conflict(code="already_processed", message=f"Application is already {req.status}.")

    full_name = body.full_name.strip() if body and body.full_name else req.full_name
    employee_no = body.employee_no.strip() if body and body.employee_no else req.employee_no
    designation = body.designation.strip() if body and body.designation else req.designation

    if employee_no and employee_no != req.employee_no:
        existing_emp = db.scalar(
            select(User.id).where(func.lower(User.employee_no) == func.lower(employee_no))
        )
        if existing_emp is not None:
            raise Conflict(
                code="employee_no_taken",
                message=f"A staff record with employee number '{employee_no}' already exists.",
            )

    unit_id, unit_name = _resolve_target_unit(db, actor, req, body)

    person = User(
        username=req.username,
        display_name=full_name,
        is_admin=False,
        must_set_password=True,
        designation=designation,
        employee_no=employee_no,
        contact_email=req.contact_email,
        contact_phone=req.contact_phone,
        joined_on=date.today(),
        home_workspace_id=unit_id,
    )
    people.set_status(person, "invited", effective_on=people.site_date(settings))
    db.add(person)
    db.flush()

    memberships.set_membership(
        db,
        actor=actor.user,
        workspace_id=unit_id,
        user_id=person.id,
        role="member",
        reason="Approved voluntary application",
    )

    code, credential = issue_credential(db, person, "activation", actor.user, settings)

    req.status = "approved"
    req.reviewed_at = utcnow()
    req.reviewed_by = actor.user.id
    req.created_user_id = person.id
    req.unit_id = unit_id
    req.unit_name = unit_name
    req.employee_no = employee_no
    req.designation = designation
    req.full_name = full_name

    audit.record(
        db,
        actor=actor.user,
        action="join_request.approved",
        scope_type="people",
        target_id=person.id,
        reason=f"Approved voluntary application for {full_name} ({req.username})",
    )

    db.commit()

    return {
        "status": "approved",
        "activation": {
            "code": code,
            "expires_at": iso(credential.expires_at),
        },
        "user": {
            "id": str(person.id),
            "username": person.username,
            "display_name": person.display_name,
        },
    }


@admin_router.post("/{request_id}/reject")
def reject_join_request(
    request_id: uuid.UUID,
    body: RejectRequest | None = None,
    actor: Actor = Depends(console_people),
    db: Session = Depends(get_db),
) -> dict:
    """Decline a voluntary application with an optional review note."""
    req = db.get(JoinRequest, request_id)
    if req is None:
        raise NotFound()
    if req.status != "pending":
        raise Conflict(code="already_processed", message=f"Application is already {req.status}.")

    reason = body.reason if body and body.reason else "Application declined by administrator"
    req.status = "rejected"
    req.reviewed_at = utcnow()
    req.reviewed_by = actor.user.id
    req.review_note = reason

    audit.record(
        db,
        actor=actor.user,
        action="join_request.rejected",
        scope_type="people",
        target_id=req.id,
        reason=reason,
    )

    db.commit()
    return {"status": "rejected", "id": str(req.id)}
