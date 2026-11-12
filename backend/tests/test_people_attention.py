"""PO-22 attention items: each is created by real state and clears when that state is fixed."""

import uuid
from datetime import date, timedelta

from sqlalchemy import select

from labadda import positions
from labadda.models import (
    CredentialToken,
    Membership,
    ScheduledChange,
    UnitPosition,
    User,
    Workspace,
)
from labadda.security import utcnow
from tests.test_changes_authority import make_head, site_today
from tests.test_panel import pair

NOW = utcnow()


def entries(admin):
    response = admin.get("/admin/org/attention")
    assert response.status_code == 200, response.text
    return {item["id"]: item for item in response.json()["items"]}


def update(db_factory, model, key, **values):
    with db_factory() as db:
        row = db.get(model, key)
        for name, value in values.items():
            setattr(row, name, value)
        db.commit()


def staff_all_units(db_factory):
    with db_factory() as db:
        asha = db.scalar(select(User).where(User.username == "asha"))
        for unit in db.scalars(select(Workspace).where(Workspace.kind == "org")):
            if not db.scalar(
                select(Membership).where(Membership.workspace_id == unit.id, Membership.user_id == asha.id)
            ):
                db.add(Membership(user_id=asha.id, workspace_id=unit.id, role="steward"))
        db.commit()


def test_units_without_steward(as_user, ids, db_factory):
    admin = as_user("admin")
    assert "people:units-without-steward" in entries(admin)
    staff_all_units(db_factory)
    assert "people:units-without-steward" not in entries(admin)
    with db_factory() as db:
        db.execute(
            Membership.__table__.delete().where(
                Membership.workspace_id == ids["workspaces"]["section_b"],
                Membership.role == "steward",
            )
        )
        db.commit()
    item = entries(admin)["people:units-without-steward"]
    assert "Catalysis Section" in item["detail"] and item["route"] == "/admin/org"


def test_people_without_a_home_unit(as_user, ids, db_factory):
    admin = as_user("admin")
    assert "people:no-home-unit" not in entries(admin)
    update(db_factory, User, ids["users"]["ben"], home_workspace_id=None)
    assert "Ben Okafor" in entries(admin)["people:no-home-unit"]["detail"]
    update(db_factory, User, ids["users"]["ben"], home_workspace_id=ids["workspaces"]["section_a"])
    assert "people:no-home-unit" not in entries(admin)


def test_activation_codes_pending_more_than_14_days(as_user, ids, db_factory):
    admin = as_user("admin")
    ben = ids["users"]["ben"]
    update(db_factory, User, ben, status="invited")
    with db_factory() as db:
        db.add(
            CredentialToken(
                user_id=uuid_of(ben),
                token_hash="a" * 64,
                purpose="activation",
                expires_at=NOW + timedelta(days=1),
                created_at=NOW - timedelta(days=15),
            )
        )
        db.commit()
    assert "people:activation-pending" in entries(admin)
    with db_factory() as db:
        db.add(
            CredentialToken(
                user_id=uuid_of(ben),
                token_hash="b" * 64,
                purpose="activation",
                expires_at=NOW + timedelta(days=1),
            )
        )
        db.commit()
    assert "people:activation-pending" not in entries(admin)


def uuid_of(value):
    return uuid.UUID(value)


def test_acting_appointments_ending_soon(as_user, ids, db_factory, settings):
    admin = as_user("admin")
    ends = site_today(settings) + timedelta(days=5)
    row = make_head(db_factory, ids, username="asha", unit="section_a", acting=True, ends_on=ends)
    assert "Thin Films Section" in entries(admin)["people:acting-ending"]["detail"]
    with db_factory() as db:
        db.get(UnitPosition, uuid_of(row)).ends_on = ends + timedelta(days=60)
        db.commit()
    assert "people:acting-ending" not in entries(admin)


def test_expired_acting_appointment_with_nobody_in_the_position(as_user, ids, db_factory, settings):
    admin = as_user("admin")
    row = make_head(
        db_factory, ids, username="asha", unit="section_a", acting=True, ends_on=site_today(settings)
    )
    with db_factory() as db:
        positions.expire_due(db, settings, now=utcnow() + timedelta(days=1))
    assert "Thin Films Section" in entries(admin)["people:acting-expired"]["detail"]
    make_head(db_factory, ids, username="dana", unit="section_a")
    assert "people:acting-expired" not in entries(admin)
    assert row


def test_overdue_returns_from_leave(as_user, ids, db_factory, settings):
    admin = as_user("admin")
    ben = ids["users"]["ben"]
    update(
        db_factory,
        User,
        ben,
        status="on_leave",
        expected_return_on=site_today(settings) - timedelta(days=1),
    )
    assert "Ben Okafor" in entries(admin)["people:overdue-leave"]["detail"]
    update(db_factory, User, ben, expected_return_on=site_today(settings) + timedelta(days=9))
    assert "people:overdue-leave" not in entries(admin)


def test_scheduled_changes_needing_review(as_user, ids, db_factory, settings):
    admin = as_user("admin")
    with db_factory() as db:
        row = ScheduledChange(
            kind="transfer",
            request={},
            plan_digest="c" * 64,
            effective_on=date(2030, 1, 7),
            state="needs_review",
            created_by=uuid_of(ids["users"]["admin"]),
            reason="Term change",
            steps=[],
        )
        db.add(row)
        db.commit()
        change_id = row.id
    assert entries(admin)["people:scheduled-review"]["title"] == "1 scheduled change needs review"
    response = admin.delete(f"/admin/changes/scheduled/{change_id}", params={"reason": "No longer needed"})
    assert response.status_code == 200
    assert "people:scheduled-review" not in entries(admin)


def test_groups_and_projects_whose_only_steward_is_inactive(as_user, ids, db_factory):
    admin = as_user("admin")
    assert "people:groups-without-steward" not in entries(admin)
    update(db_factory, User, ids["users"]["dana"], is_active=False)
    assert "Project Aurora" in entries(admin)["people:groups-without-steward"]["detail"]
    update(db_factory, User, ids["users"]["dana"], is_active=True)
    assert "people:groups-without-steward" not in entries(admin)


def test_accounts_never_signed_in_after_90_days(as_user, ids, db_factory, settings):
    admin = as_user("admin")
    eli = ids["users"]["eli"]
    update(db_factory, User, eli, created_at=NOW - timedelta(days=100), last_seen_on=None)
    assert "Eli Novak" in entries(admin)["people:never-signed-in"]["detail"]
    update(db_factory, User, eli, last_seen_on=site_today(settings))
    assert "people:never-signed-in" not in entries(admin)


def test_attention_endpoint_is_for_administrators_only(as_user, ids, make_client):
    assert as_user("ben").get("/admin/org/attention").status_code == 403
    assert make_client().get("/admin/org/attention").status_code == 401
    assert pair(as_user, make_client, ids).get("/admin/org/attention").status_code == 401


def test_overview_carries_the_same_people_items(as_user, ids):
    overview = as_user("admin").get("/admin/overview").json()["attention"]
    assert "people:units-without-steward" in {entry["id"] for entry in overview}


def test_entries_hold_names_and_counts_only(as_user, ids, db_factory):
    update(db_factory, User, ids["users"]["ben"], home_workspace_id=None)
    text = as_user("admin").get("/admin/org/attention").text
    assert "Recognisable" not in text
