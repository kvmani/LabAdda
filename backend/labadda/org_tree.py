"""Organisation chart data (PO-21): units, spaces and counts. Names, roles and counts only."""

from __future__ import annotations

import uuid
from collections import defaultdict

from sqlalchemy import func, select
from sqlalchemy.orm import Session, aliased

from .models import Membership, UnitAdminGrant, UnitPosition, User, Workspace
from .serialize import iso


def _person(user: User) -> dict:
    return {"id": str(user.id), "name": user.display_name}


def _stewards(db: Session) -> dict[uuid.UUID, list[dict]]:
    rows = db.execute(
        select(Membership.workspace_id, User)
        .join(User, User.id == Membership.user_id)
        .where(Membership.role == "steward", User.is_active.is_(True))
        .order_by(User.display_name, User.id)
    )
    found: dict[uuid.UUID, list[dict]] = defaultdict(list)
    for workspace_id, user in rows:
        found[workspace_id].append(_person(user))
    return found


def _heads(db: Session) -> dict[tuple[uuid.UUID, bool], dict]:
    rows = db.execute(
        select(UnitPosition.workspace_id, UnitPosition.acting, User)
        .join(User, User.id == UnitPosition.user_id)
        .where(UnitPosition.position == "head", UnitPosition.ended_at.is_(None))
    )
    return {(workspace_id, acting): _person(user) for workspace_id, acting, user in rows}


def _counts(db: Session) -> tuple[dict[uuid.UUID, int], dict[uuid.UUID, int]]:
    homes = dict(
        db.execute(
            select(User.home_workspace_id, func.count())
            .where(User.home_workspace_id.is_not(None))
            .group_by(User.home_workspace_id)
        ).all()
    )
    members = dict(
        db.execute(select(Membership.workspace_id, func.count()).group_by(Membership.workspace_id)).all()
    )
    return homes, members


def _parent(row: Workspace, scope: frozenset[uuid.UUID] | None) -> str | None:
    if row.parent_id is None or (scope is not None and row.parent_id not in scope):
        return None
    return str(row.parent_id)


def tree(db: Session, scope: frozenset[uuid.UUID] | None = None) -> dict:
    """Every unit with its Head, stewards and counts, plus projects and groups listed beside it.

    A unit administrator's ``scope`` keeps only their branch, as a tree of its own: the unit they
    administer has no visible parent, and projects and groups are not listed.
    """
    stewards, heads = _stewards(db), _heads(db)
    homes, members = _counts(db)
    rows = db.scalars(select(Workspace).order_by(Workspace.name, Workspace.id)).all()
    units, spaces = [], []
    for row in rows:
        if scope is not None and row.id not in scope:
            continue
        common = {"id": str(row.id), "name": row.name, "archived": row.archived}
        if row.kind == "org":
            units.append(
                {
                    **common,
                    "code": row.code,
                    "level": row.level,
                    "parent_id": _parent(row, scope),
                    "head": heads.get((row.id, False)),
                    "acting_head": heads.get((row.id, True)),
                    "stewards": stewards.get(row.id, []),
                    "people": homes.get(row.id, 0),
                    "members": members.get(row.id, 0),
                }
            )
        else:
            spaces.append(
                {
                    **common,
                    "kind": row.kind,
                    "stewards": stewards.get(row.id, []),
                    "members": members.get(row.id, 0),
                }
            )
    return {"units": units, "spaces": spaces}


def unit_administrators(db: Session) -> dict:
    """Current appointments (PO-24): who administers which unit, by whom and since when."""
    granter = aliased(User)
    rows = db.execute(
        select(UnitAdminGrant, User, Workspace, granter.display_name)
        .join(User, User.id == UnitAdminGrant.user_id)
        .join(Workspace, Workspace.id == UnitAdminGrant.workspace_id)
        .join(granter, granter.id == UnitAdminGrant.granted_by)
        .where(UnitAdminGrant.revoked_at.is_(None))
        .order_by(Workspace.name, User.display_name, UnitAdminGrant.id)
    ).all()
    return {
        "items": [
            {
                "id": str(grant.id),
                "person": _person(person),
                "unit": {"id": str(unit.id), "name": unit.name, "archived": unit.archived},
                "granted_by": by,
                "granted_at": iso(grant.granted_at),
            }
            for grant, person, unit, by in rows
        ]
    }
