"""Protected staff profiles and grant/history metadata, without private content."""

import uuid
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import policy
from .config import Settings
from .errors import NotFound
from .models import AuditEvent, User, Workspace
from .people_directory import DirectoryFilters, directory_query, person_json

SUMMARIES = {
    "people.change": "Reviewed staff change applied",
    "people.change_step": "Staff record updated",
    "identity.create": "Account created",
    "identity.update": "Account updated",
    "identity.reset": "Password reset requested",
    "auth.login": "Sign-in recorded",
    "auth.activation_redeemed": "Account activated",
    "auth.reset_redeemed": "Password reset completed",
    "membership.set": "Workspace membership set",
    "membership.remove": "Workspace membership removed",
    "usage.reader.grant": "Operational read access granted",
    "usage.reader.revoke": "Operational read access revoked",
}


def require_person(db: Session, identity: uuid.UUID) -> User:
    """Reject missing people uniformly after the caller has checked administration."""
    person = db.get(User, identity, populate_existing=True)
    if person is None:
        raise NotFound()
    return person


def profile(db: Session, identity: uuid.UUID) -> dict:
    """Return only the explicit staff record; contacts are absent from bulk listings."""
    row = db.execute(
        directory_query(db, DirectoryFilters())
        .where(User.id == identity)
        .execution_options(populate_existing=True)
    ).first()
    if row is None:
        raise NotFound()
    person, unit = row
    payload = person_json(person, unit)
    payload.update(contact_email=person.contact_email, contact_phone=person.contact_phone)
    for name in ("status_effective_on", "expected_return_on", "joined_on"):
        value = getattr(person, name)
        payload[name] = value.isoformat() if value else None
    return payload


def access_page(db: Session, identity: uuid.UUID, limit: int, cursor: uuid.UUID | None) -> dict:
    """Show retained direct grants and upward-only inheritance, including blocked accounts."""
    person = require_person(db, identity)
    direct = policy.direct_grants(db, identity)
    parents = dict(db.execute(select(Workspace.id, Workspace.parent_id).where(Workspace.kind == "org")).all())
    roles = dict(direct)
    for workspace_id in direct:
        if workspace_id in parents:
            for ancestor in policy.ancestors(parents, workspace_id):
                roles.setdefault(ancestor, "member")
    identities = [key for key in sorted(roles) if cursor is None or key > cursor]
    selected = identities[:limit]
    rows = db.scalars(select(Workspace).where(Workspace.id.in_(selected)).order_by(Workspace.id)).all()
    return {
        "memberships": [
            {
                "workspace": {
                    "id": str(space.id),
                    "name": space.name,
                    "kind": space.kind,
                    "archived": space.archived,
                },
                "role": roles[space.id],
                "inherited": space.id not in direct,
                "sign_in_enabled": person.is_active and not person.must_set_password,
            }
            for space in rows
        ],
        "next_cursor": str(selected[-1]) if len(identities) > limit else None,
    }


def timeline_page(
    db: Session, identity: uuid.UUID, settings: Settings, limit: int, before: int | None
) -> dict:
    """Expose plain staff history and calendar dates; never forward raw audit JSON."""
    require_person(db, identity)
    query = (
        select(AuditEvent, User)
        .outerjoin(User, User.id == AuditEvent.actor_id)
        .where(AuditEvent.target_id == str(identity), AuditEvent.scope_type.in_(("identity", "workspace")))
        .order_by(AuditEvent.id.desc())
        .limit(limit + 1)
    )
    if before is not None:
        query = query.where(AuditEvent.id < before)
    rows = db.execute(query).all()
    items = []
    for event, actor in rows[:limit]:
        known = event.action in SUMMARIES
        summary = SUMMARIES.get(event.action, "Staff-related activity recorded")
        if event.action == "auth.login" and event.outcome == "denied":
            summary = "Sign-in unsuccessful"
        items.append(
            {
                "id": event.id,
                "occurred_on": event.created_at.astimezone(ZoneInfo(settings.timezone)).date().isoformat(),
                "actor": {"id": str(actor.id), "display_name": actor.display_name} if actor else None,
                "summary": summary,
                "reason": event.reason[:500] if known and event.reason else None,
                "outcome": event.outcome if event.outcome in {"success", "denied"} else "unknown",
            }
        )
    return {"items": items, "next_cursor": items[-1]["id"] if len(rows) > limit else None}
