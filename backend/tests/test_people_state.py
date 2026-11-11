"""P1 staff state preserves legacy authentication and date-only observations."""

from dataclasses import replace
from datetime import UTC, date, datetime

import pytest

from labadda import people
from labadda.models import User
from tests.test_panel import PANEL, pair


@pytest.mark.parametrize(
    ("status", "allowed"),
    [
        ("invited", True),
        ("active", True),
        ("on_leave", True),
        ("suspended", False),
        ("retired", False),
        ("left", False),
    ],
)
def test_status_derives_access_switch(status, allowed):
    user = User(username="synthetic", display_name="Synthetic", must_set_password=False)
    people.set_status(user, status, effective_on=date(2026, 11, 11))
    assert user.is_active is allowed
    assert user.status == status
    assert user.revision == 1
    assert user.status_effective_on == date(2026, 11, 11)
    if status == "invited":
        assert user.must_set_password


def test_site_date_uses_site_calendar(settings):
    instant = datetime(2026, 11, 10, 20, tzinfo=UTC)
    assert people.site_date(replace(settings, timezone="Asia/Kolkata"), now=instant) == date(2026, 11, 11)
    assert people.site_date(replace(settings, timezone="UTC"), now=instant) == date(2026, 11, 10)


def test_sign_in_observation_is_date_only_and_monotonic(db_factory, ids, settings):
    with db_factory() as db:
        user = db.get(User, ids["users"]["ben"])
        current_revision = user.revision
        people.record_sign_in(db, user, settings, now=datetime(2026, 11, 11, tzinfo=UTC))
        people.record_sign_in(db, user, settings, now=datetime(2026, 11, 10, tzinfo=UTC))
        db.commit()
        db.refresh(user)
        assert type(user.last_seen_on) is date
        assert user.last_seen_on == date(2026, 11, 11)
        assert user.revision == current_revision


def test_invitation_activation_and_legacy_disable_keep_status_consistent(as_user, make_client, db_factory):
    admin = as_user("admin")
    response = admin.post("/admin/users", json={"username": "newstaff", "display_name": "New Staff"})
    assert response.status_code == 201
    account_id = response.json()["user"]["id"]
    with db_factory() as db:
        user = db.get(User, account_id)
        assert user.status == "invited"
        assert user.is_active and user.must_set_password
    client = make_client()
    activated = client.post(
        "/auth/activate",
        json={"token": response.json()["activation_token"], "password": "synthetic-password-123"},
    )
    assert activated.status_code == 200
    with db_factory() as db:
        user = db.get(User, account_id)
        assert user.status == "active"
        assert type(user.last_seen_on) is date
        assert user.revision == 2
    assert admin.patch(f"/admin/users/{account_id}", json={"is_active": False}).status_code == 200
    assert client.get("/auth/session").status_code == 401
    with db_factory() as db:
        user = db.get(User, account_id)
        assert user.status == "left"
        assert not user.is_active
        assert user.revision == 3


def test_panel_claim_does_not_record_a_normal_sign_in(as_user, make_client, ids, db_factory):
    desktop = as_user("asha")
    with db_factory() as db:
        date_before = db.get(User, ids["users"]["asha"]).last_seen_on
    kiosk = pair(as_user, make_client, ids, user="asha")
    assert kiosk.get("/admin/console").status_code == 401
    assert desktop.get("/admin/console", headers=PANEL).status_code == 401
    with db_factory() as db:
        assert db.get(User, ids["users"]["asha"]).last_seen_on == date_before


def test_blocked_leave_is_explicit_and_cannot_be_applied_to_another_status():
    user = User(username="synthetic", display_name="Synthetic", must_set_password=False)
    people.set_status(user, "on_leave", leave_sign_in=False)
    assert not user.is_active
    assert user.status == "on_leave"
    people.set_status(user, "on_leave", leave_sign_in=True)
    assert user.is_active
    assert user.revision == 2
    with pytest.raises(ValueError, match="only applies"):
        people.set_status(user, "active", leave_sign_in=False)
    assert user.status == "on_leave" and user.is_active


def test_status_transitions_are_audited(as_user, make_client, db_factory):
    from sqlalchemy import select

    from labadda.models import AuditEvent

    created = as_user("admin").post(
        "/admin/users", json={"username": "audited", "display_name": "Audited Staff"}
    )
    assert created.status_code == 201
    account_id = created.json()["user"]["id"]
    assert (
        make_client()
        .post(
            "/auth/activate",
            json={"token": created.json()["activation_token"], "password": "synthetic-password-123"},
        )
        .status_code
        == 200
    )
    assert as_user("admin").patch(f"/admin/users/{account_id}", json={"is_active": False}).status_code == 200
    with db_factory() as db:
        rows = db.scalars(select(AuditEvent).where(AuditEvent.target_id == account_id)).all()
        transitions = {
            row.action: (row.detail.get("status_before"), row.detail.get("status_after")) for row in rows
        }
    assert transitions["identity.create"] == (None, "invited")
    assert transitions["auth.activation_redeemed"] == ("invited", "active")
    assert transitions["identity.update"] == ("active", "left")


def test_legacy_access_toggle_preserves_leave_state(as_user, ids, db_factory):
    with db_factory() as db:
        person = db.get(User, ids["users"]["ben"])
        people.set_status(person, "on_leave", leave_sign_in=False)
        db.commit()
    assert (
        as_user("admin").patch(f"/admin/users/{ids['users']['ben']}", json={"is_active": True}).status_code
        == 200
    )
    with db_factory() as db:
        person = db.get(User, ids["users"]["ben"])
        assert person.status == "on_leave"
        assert person.is_active


def test_naive_observation_clock_is_refused(settings):
    with pytest.raises(ValueError, match="timezone-aware"):
        people.site_date(settings, now=datetime(2026, 11, 11))
