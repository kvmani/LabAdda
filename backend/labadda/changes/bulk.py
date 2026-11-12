"""One reviewed, atomic change made of many ordinary changes (spreadsheet import, multi-select)."""

import hmac
import uuid
from dataclasses import asdict
from hashlib import sha256
from typing import Annotated

from pydantic import BaseModel, Field, field_validator, model_validator
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .. import people
from ..config import Settings
from ..deps import Actor
from ..errors import Conflict, Invalid
from ..models import User
from ..realtime import Hub
from . import service
from .plan import Plan, canonical_json
from .requests import (
    AddPerson,
    EditPerson,
    Reason,
    Revision,
    Suspend,
    Transfer,
    _ordinary_reason,
)

MAX_REQUESTS = 2000
type BulkItem = Annotated[AddPerson | EditPerson | Transfer | Suspend, Field(discriminator="kind")]


class BulkPreview(BaseModel):
    """The ordinary staff changes to review together; steps are always rebuilt on the server."""

    requests: list[BulkItem] = Field(min_length=1, max_length=MAX_REQUESTS)

    @model_validator(mode="after")
    def distinct(self) -> "BulkPreview":
        """Two changes of one kind to one person would be built from the same old state."""
        seen = set()
        for item in self.requests:
            key = (item.kind, item.username if isinstance(item, AddPerson) else item.person_id)
            if key in seen:
                raise ValueError("Each person can appear once for each kind of change.")
            seen.add(key)
        return self


class BulkApply(BulkPreview):
    """Confirm exactly the reviewed requests, consequences and record revisions."""

    digest: str = Field(pattern="^[a-f0-9]{64}$", strict=True)
    revisions: dict[uuid.UUID, Revision] = Field(max_length=MAX_REQUESTS)
    reason: Reason

    @field_validator("reason")
    @classmethod
    def valid_reason(cls, value: str) -> str:
        return _ordinary_reason(value)


def _label(db: Session, item: BulkItem) -> str:
    if isinstance(item, AddPerson):
        return item.display_name
    person = db.get(User, item.person_id)
    return person.display_name if person else "Unknown person"


def _plans(db: Session, body: BulkPreview, actor_id: uuid.UUID, settings: Settings) -> list[Plan]:
    return [service.build(db, item, actor_id, settings) for item in body.requests]


def _digest(actor_id: uuid.UUID, plans: list[Plan]) -> str:
    payload = {
        "format_version": 1,
        "kind": "bulk",
        "actor_id": str(actor_id),
        "plans": [p.digest for p in plans],
    }
    return sha256(canonical_json(payload).encode("utf-8")).hexdigest()


def _revisions(plans: list[Plan]) -> dict[str, int]:
    merged: dict[str, int] = {}
    for plan in plans:
        merged.update(plan.revisions.to_dict())
    return merged


def preview(db: Session, actor: Actor, settings: Settings, body: BulkPreview) -> dict:
    """Merge the rebuilt plans; blockers say whose change they belong to."""
    user = service.authorize(db, actor, settings)
    plans = _plans(db, body, user.id, settings)
    blockers = []
    for item, plan in zip(body.requests, plans, strict=True):
        label = _label(db, item)
        blockers += [{**asdict(b), "message": f"{label}: {b.message}"} for b in plan.blockers]
    payload = {
        "kind": "bulk",
        "count": len(plans),
        "steps": [step.to_dict() for plan in plans for step in plan.steps],
        "warnings": [asdict(w) for plan in plans for w in plan.warnings],
        "blockers": blockers,
        "revisions": _revisions(plans),
        "affected_people": sum(plan.affected_people for plan in plans),
        "digest": _digest(user.id, plans),
    }
    service.authorize(db, actor, settings)
    return payload


def _commit(db: Session, user: User, body: BulkApply, settings: Settings) -> tuple[dict, list[tuple]]:
    for item in body.requests:
        service.lock_targets(db, item)
    plans = _plans(db, body, user.id, settings)
    revisions = {str(identity): revision for identity, revision in body.revisions.items()}
    if not hmac.compare_digest(_digest(user.id, plans), body.digest) or revisions != _revisions(plans):
        raise Conflict("plan_stale", "This record or its consequences changed. Review a fresh plan.")
    if any(plan.blockers for plan in plans):
        raise Invalid("plan_blocked", "Resolve the blocking problems before applying this change.")
    done, added = [], []
    for index, (item, plan) in enumerate(zip(body.requests, plans, strict=True)):
        if index and service.build(db, item, user.id, settings).blockers:
            # Plans above were built from the state before any row applied; earlier rows can
            # together defeat a guard (two stewards leaving one unit), so recheck on current state.
            raise Invalid("plan_blocked", "Resolve the blocking problems before applying this change.")
        person, extra = service.KINDS[plan.kind].apply(db, user, plan, item, settings, body.reason)
        service.record_plan(db, user, plan, body.reason, settings, person.id)
        done.append((person, plan))
        if isinstance(item, AddPerson):
            added.append(
                {
                    "person_id": str(person.id),
                    "username": item.username,
                    "display_name": item.display_name,
                    **extra,
                }
            )
    db.commit()
    receipt = {
        "applied": True,
        "kind": "bulk",
        "digest": body.digest,
        "count": len(done),
        "added": added,
        "site_date": people.site_date(settings).isoformat(),
    }
    return receipt, done


def apply(db: Session, actor: Actor, settings: Settings, body: BulkApply, hub: Hub) -> dict:
    """All selected changes commit together or none do."""
    try:
        user = service.authorize(db, actor, settings)
        receipt, done = _commit(db, user, body, settings)
    except IntegrityError:
        db.rollback()
        raise Conflict("plan_stale", "Staff information changed. Review a fresh plan.") from None
    except Exception:
        db.rollback()
        raise
    for person, plan in done:
        service.revalidate(hub, person, plan)
    return receipt
