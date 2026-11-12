"""People items on the attention list (PO-22): each is one bounded query of names and a count.

Every item clears itself when the underlying state is fixed, because it is read live and nothing
is stored. Entries hold unit and people names, counts and dates only; never user content (AD-02).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from sqlalchemy import Select, String, func, select
from sqlalchemy.orm import Session, aliased

from .. import people
from ..config import Settings
from ..models import CredentialToken, Membership, ScheduledChange, UnitPosition, User, Workspace

MAX_NAMES = 3
ACTING_WARNING_DAYS = 14
ACTIVATION_DAYS = 14
NEVER_SIGNED_IN_DAYS = 90
EXPIRED_LOOKBACK_DAYS = 60
STAFF_STATUSES = ("invited", "active", "on_leave")
Expired = aliased(UnitPosition, name="expired")


@dataclass(frozen=True)
class Item:
    key: str
    severity: str
    one: str
    many: str
    advice: str
    route: str
    names: Callable[[datetime, date], Select]


def _active_steward(workspace_id=Workspace.id):
    return (
        select(Membership.id)
        .join(User, User.id == Membership.user_id)
        .where(
            Membership.workspace_id == workspace_id,
            Membership.role == "steward",
            User.is_active.is_(True),
        )
        .exists()
    )


def _units_without_steward(now, today) -> Select:
    return select(Workspace.name).where(
        Workspace.kind == "org", Workspace.archived.is_(False), ~_active_steward()
    )


def _no_home_unit(now, today) -> Select:
    return select(User.display_name).where(
        User.is_active.is_(True),
        User.is_admin.is_(False),
        User.status.in_(STAFF_STATUSES),
        User.home_workspace_id.is_(None),
    )


def _activation_pending(now, today) -> Select:
    newest = (
        select(CredentialToken.user_id, func.max(CredentialToken.created_at).label("issued"))
        .where(CredentialToken.purpose == "activation")
        .group_by(CredentialToken.user_id)
        .subquery()
    )
    return (
        select(User.display_name)
        .join(newest, newest.c.user_id == User.id)
        .where(User.status == "invited", newest.c.issued < now - timedelta(days=ACTIVATION_DAYS))
    )


def _acting_ending(now, today) -> Select:
    return (
        select(Workspace.name)
        .join(UnitPosition, UnitPosition.workspace_id == Workspace.id)
        .where(
            UnitPosition.acting.is_(True),
            UnitPosition.ended_at.is_(None),
            UnitPosition.ends_on <= today + timedelta(days=ACTING_WARNING_DAYS),
        )
    )


def _acting_expired(now, today) -> Select:
    """An acting term ended recently and nobody holds that position now: a permanent decision is due."""
    held = (
        select(UnitPosition.id)
        .where(
            UnitPosition.workspace_id == Workspace.id,
            UnitPosition.position == Expired.position,
            UnitPosition.ended_at.is_(None),
        )
        .exists()
    )
    return (
        select(Workspace.name)
        .join(Expired, Expired.workspace_id == Workspace.id)
        .where(
            Expired.acting.is_(True),
            Expired.end_reason == "expired",
            Expired.ended_at >= now - timedelta(days=EXPIRED_LOOKBACK_DAYS),
            Workspace.archived.is_(False),
            ~held,
        )
    )


def _overdue_leave(now, today) -> Select:
    return select(User.display_name).where(User.status == "on_leave", User.expected_return_on < today)


def _groups_without_steward(now, today) -> Select:
    return select(Workspace.name).where(
        Workspace.kind.in_(("project", "group")), Workspace.archived.is_(False), ~_active_steward()
    )


def _never_signed_in(now, today) -> Select:
    return select(User.display_name).where(
        User.is_active.is_(True),
        User.status.in_(("invited", "active")),
        User.last_seen_on.is_(None),
        User.created_at < now - timedelta(days=NEVER_SIGNED_IN_DAYS),
    )


def _needs_review(now, today) -> Select:
    return select(func.concat("Change on ", func.to_char(ScheduledChange.effective_on, "DD Mon YYYY"))).where(
        ScheduledChange.state == "needs_review"
    )


ITEMS = (
    Item(
        "units-without-steward",
        "warning",
        "1 unit has no steward or Head",
        "{n} units have no steward or Head",
        "Appoint someone so requests and questions have an owner.",
        "/admin/org",
        _units_without_steward,
    ),
    Item(
        "no-home-unit",
        "warning",
        "1 person has no home unit",
        "{n} people have no home unit",
        "Transfer them to a unit so they can see their unit's noticeboard.",
        "/admin/people",
        _no_home_unit,
    ),
    Item(
        "activation-pending",
        "info",
        "1 activation code has waited more than 14 days",
        "{n} activation codes have waited more than 14 days",
        "Print a new activation slip, or check that they are still joining.",
        "/admin/people?status=invited",
        _activation_pending,
    ),
    Item(
        "acting-ending",
        "warning",
        "1 acting appointment ends within 14 days",
        "{n} acting appointments end within 14 days",
        "Make the appointment permanent, extend it or appoint someone else.",
        "/admin/org",
        _acting_ending,
    ),
    Item(
        "acting-expired",
        "warning",
        "1 acting appointment has ended and the position is empty",
        "{n} acting appointments have ended and their positions are empty",
        "Appoint a Head or Deputy.",
        "/admin/org",
        _acting_expired,
    ),
    Item(
        "overdue-leave",
        "warning",
        "1 person is past their expected return from leave",
        "{n} people are past their expected return from leave",
        "Record their return or change the date.",
        "/admin/people?status=on_leave",
        _overdue_leave,
    ),
    Item(
        "scheduled-review",
        "error",
        "1 scheduled change needs review",
        "{n} scheduled changes need review",
        "It was not applied. Open the scheduled list to see why.",
        "/admin/people",
        _needs_review,
    ),
    Item(
        "groups-without-steward",
        "warning",
        "1 project or group has no active steward",
        "{n} projects or groups have no active steward",
        "Choose a steward so members have someone to ask.",
        "/admin/org",
        _groups_without_steward,
    ),
    Item(
        "never-signed-in",
        "info",
        "1 account has never signed in after 90 days",
        "{n} accounts have never signed in after 90 days",
        "Check whether they still need access.",
        "/admin/people?status=active",
        _never_signed_in,
    ),
)


def people_entries(db: Session, settings: Settings, now: datetime) -> list[dict]:
    """One entry per item that currently has something to report; names are shown three at a time."""
    today = people.site_date(settings, now=now)
    entries = []
    for item in ITEMS:
        names = item.names(now, today)
        column = names.selected_columns[0]
        rows = db.execute(
            names.add_columns(func.count().over()).order_by(func.lower(column.cast(String))).limit(MAX_NAMES)
        ).all()
        if not rows:
            continue
        count = rows[0][1]
        shown = ", ".join(str(row[0]) for row in rows) + (" and others" if count > len(rows) else "")
        entries.append(
            {
                "id": f"people:{item.key}",
                "kind": "people",
                "severity": item.severity,
                "status": None,
                "title": item.one if count == 1 else item.many.format(n=count),
                "detail": f"{shown}. {item.advice}",
                "route": item.route,
                "help": None,
                "at": None,
            }
        )
    return entries
