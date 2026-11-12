"""Unit positions (PO-13 to PO-16): Head, Deputy and additional charges, and their dated expiry.

A Head or Deputy is always a steward of the unit while the position is current; an additional
charge records access in a second unit that may end on a date. Ended rows are kept as history.
Membership writes stay in ``memberships``; this module only records and ends positions.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from . import audit, memberships, people
from .config import Settings
from .models import UnitPosition, User, Workspace
from .realtime import Hub
from .security import utcnow

type PositionKind = Literal["head", "deputy", "charge"]
type RevertRole = Literal["member", "steward", "none"]
LABELS = {"head": "Head", "deputy": "Deputy", "charge": "Additional charge"}


def title(row: UnitPosition) -> str:
    """Plain words for a position, e.g. "acting Head"."""
    return f"acting {LABELS[row.position]}" if row.acting else LABELS[row.position]


def current(
    db: Session, *, user_id: uuid.UUID | None = None, workspace_id: uuid.UUID | None = None
) -> list[UnitPosition]:
    """Current positions, oldest first, for one person, one unit or both."""
    query = select(UnitPosition).where(UnitPosition.ended_at.is_(None))
    if user_id is not None:
        query = query.where(UnitPosition.user_id == user_id)
    if workspace_id is not None:
        query = query.where(UnitPosition.workspace_id == workspace_id)
    return list(db.scalars(query.order_by(UnitPosition.created_at, UnitPosition.id)))


def current_head(db: Session, workspace_id: uuid.UUID, *, acting: bool) -> UnitPosition | None:
    """The unit's substantive or acting Head; the partial unique index allows one of each."""
    return db.scalar(
        select(UnitPosition).where(
            UnitPosition.workspace_id == workspace_id,
            UnitPosition.position == "head",
            UnitPosition.acting.is_(acting),
            UnitPosition.ended_at.is_(None),
        )
    )


def role_before(db: Session, user_id: uuid.UUID, workspace_id: uuid.UUID) -> RevertRole:
    """The direct role an appointment returns to when it ends."""
    role = memberships.direct_role(db, user_id, workspace_id)
    return "steward" if role == "steward" else "member" if role == "member" else "none"


def appoint(
    db: Session,
    *,
    actor: User,
    workspace_id: uuid.UUID,
    user_id: uuid.UUID,
    position: PositionKind,
    starts_on: date,
    ends_on: date | None = None,
    acting: bool = False,
    revert_role: RevertRole | None = None,
    covers_id: uuid.UUID | None = None,
    reason: str | None = None,
) -> UnitPosition:
    """Record a position in the caller's transaction; the caller sets the membership first."""
    row = UnitPosition(
        workspace_id=workspace_id,
        user_id=user_id,
        position=position,
        acting=acting,
        starts_on=starts_on,
        ends_on=ends_on,
        revert_role=revert_role,
        covers_id=covers_id,
        created_by=actor.id,
    )
    db.add(row)
    db.flush()
    audit.record(
        db,
        actor=actor,
        action="position.appoint",
        scope_type="workspace",
        scope_id=workspace_id,
        target_id=user_id,
        reason=reason,
        position=position,
        acting=acting,
        ends_on=ends_on.isoformat() if ends_on else None,
    )
    return row


def end(
    db: Session,
    row: UnitPosition,
    *,
    actor: User | None,
    reason: str | None,
    end_reason: Literal["expired", "ended"] = "ended",
    now: datetime | None = None,
) -> None:
    """End one current position, keeping the row as history."""
    if row.ended_at is not None:
        return
    row.ended_at = now or utcnow()
    row.end_reason = end_reason
    audit.record(
        db,
        actor=actor,
        action="position.expire" if end_reason == "expired" else "position.end",
        scope_type="workspace",
        scope_id=row.workspace_id,
        target_id=row.user_id,
        reason=reason,
        position=row.position,
        acting=row.acting,
    )
    db.flush()


def end_held(
    db: Session,
    user_id: uuid.UUID,
    workspace_id: uuid.UUID,
    *,
    actor: User | None,
    reason: str | None,
    kinds: tuple[str, ...] = ("head", "deputy", "charge"),
) -> None:
    """End positions that can no longer stand once a membership is removed or demoted."""
    for row in current(db, user_id=user_id, workspace_id=workspace_id):
        if row.position in kinds:
            end(db, row, actor=actor, reason=reason)


def revert(db: Session, row: UnitPosition, *, actor: User | None, reason: str | None) -> None:
    """Return the holder to the role the plan recorded; ``none`` removes the membership."""
    if row.revert_role is None:
        return
    if row.revert_role == "none":
        memberships.remove_membership(
            db, actor=actor, workspace_id=row.workspace_id, user_id=row.user_id, reason=reason
        )
    elif memberships.direct_role(db, row.user_id, row.workspace_id) != row.revert_role:
        memberships.set_membership(
            db,
            actor=actor,
            workspace_id=row.workspace_id,
            user_id=row.user_id,
            role=row.revert_role,
            reason=reason,
        )


EXPIRY_REASON = "The appointment reached its end date."


def expire_due(
    db: Session, settings: Settings, now: datetime | None = None, batch: int = 100, hub: Hub | None = None
) -> int:
    """End positions whose end date has arrived and apply their recorded role; idempotent.

    The ``position.expire`` audit row and the ended acting row are what the P5 attention list
    reads to ask for a permanent decision. Units are locked like every membership writer.
    """
    now = now or utcnow()
    today = people.site_date(settings, now=now)
    due = db.execute(
        select(UnitPosition.id, UnitPosition.workspace_id)
        .where(UnitPosition.ended_at.is_(None), UnitPosition.ends_on <= today)
        .order_by(UnitPosition.ends_on, UnitPosition.id)
        .limit(batch)
    ).all()
    for workspace_id in sorted({workspace for _, workspace in due}, key=str):
        memberships.lock_workspace_roles(db, workspace_id)
    ended = 0
    touched: list[tuple[uuid.UUID, uuid.UUID]] = []
    for position_id, _ in due:
        row = db.scalar(
            select(UnitPosition)
            .where(UnitPosition.id == position_id, UnitPosition.ended_at.is_(None))
            .with_for_update(skip_locked=True)
        )
        if row is None:
            continue
        end(db, row, actor=None, reason=EXPIRY_REASON, end_reason="expired", now=now)
        revert(db, row, actor=None, reason=EXPIRY_REASON)
        touched.append((row.user_id, row.workspace_id))
        ended += 1
    db.commit()
    if hub is not None:
        # Like a live apply: sockets of the holder and of the unit must drop what the role end removed.
        for user_id, workspace_id in touched:
            hub.revalidate_user(user_id)
            hub.revalidate_workspace(workspace_id)
    return ended


def expiry_job(factory: sessionmaker, settings: Settings, hub: Hub | None = None):
    """Scheduler step: one bounded pass per tick."""

    def expire_positions() -> None:
        with factory() as db:
            expire_due(db, settings, hub=hub)

    return expire_positions


def positions_by_person(
    db: Session, user_ids: list[uuid.UUID], scope: frozenset[uuid.UUID] | None = None
) -> dict[uuid.UUID, list[dict]]:
    """Current positions of a bounded set of people as unit names and dates only (one query).

    ``scope`` keeps a unit administrator to positions in their own units.
    """
    if not user_ids:
        return {}
    query = (
        select(UnitPosition, Workspace)
        .join(Workspace, Workspace.id == UnitPosition.workspace_id)
        .where(UnitPosition.user_id.in_(user_ids), UnitPosition.ended_at.is_(None))
        .order_by(Workspace.name, UnitPosition.position, UnitPosition.acting)
    )
    if scope is not None:
        query = query.where(UnitPosition.workspace_id.in_(scope))
    rows = db.execute(query).all()
    result: dict[uuid.UUID, list[dict]] = {}
    for row, space in rows:
        result.setdefault(row.user_id, []).append(
            {
                "id": str(row.id),
                "workspace": {"id": str(space.id), "name": space.name},
                "position": row.position,
                "acting": row.acting,
                "starts_on": row.starts_on.isoformat(),
                "ends_on": row.ends_on.isoformat() if row.ends_on else None,
            }
        )
    return result
