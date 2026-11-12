"""Names of people who may take over a position or a steward role in one workspace (PO-08)."""

import uuid

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from ..errors import NotFound
from ..models import Membership, User, Workspace
from .guards import unit_branch

LIMIT = 200


def candidates(db: Session, workspace_id: uuid.UUID) -> dict:
    """Active people of a unit's branch or members of a project/group; names and roles only."""
    space = db.get(Workspace, workspace_id)
    if space is None:
        raise NotFound()
    members = select(Membership.user_id).where(Membership.workspace_id == space.id)
    query = select(User).where(User.status == "active", User.is_active.is_(True))
    if space.kind == "org":
        query = query.where(or_(User.home_workspace_id.in_(unit_branch(db, space.id)), User.id.in_(members)))
    else:
        query = query.where(User.id.in_(members))
    rows = db.scalars(query.order_by(User.display_name, User.id).limit(LIMIT + 1)).all()
    roles = dict(
        db.execute(
            select(Membership.user_id, Membership.role).where(
                Membership.workspace_id == space.id, Membership.user_id.in_([row.id for row in rows])
            )
        ).all()
    )
    return {
        "workspace": {"id": str(space.id), "name": space.name, "kind": space.kind},
        "people": [
            {
                "id": str(row.id),
                "display_name": row.display_name,
                "username": row.username,
                "role": roles.get(row.id),
            }
            for row in rows[:LIMIT]
        ],
        "truncated": len(rows) > LIMIT,
    }
