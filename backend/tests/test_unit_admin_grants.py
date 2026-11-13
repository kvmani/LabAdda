"""P7 slice 1: unit-administrator storage, appoint/withdraw changes and their audit."""

import uuid

import pytest
from alembic import command
from sqlalchemy import create_engine, select, text
from sqlalchemy.exc import IntegrityError

from labadda import policy
from labadda.cli import alembic_config
from labadda.models import AuditEvent, UnitAdminGrant, User
from tests.conftest import recreate_schema
from tests.test_changes_edit import reviewed
from tests.unit_admin_support import apply_reviewed, appoint, grant_request, preview


def ids_uuid(ids, key):
    return uuid.UUID(ids["workspaces"][key])


def rows(db_factory, ids, username):
    with db_factory() as db:
        return db.scalars(
            select(UnitAdminGrant).where(UnitAdminGrant.user_id == ids["users"][username])
        ).all()


def test_site_administrator_appoints_and_withdraws_with_audit(as_user, ids, db_factory):
    admin = as_user("admin")
    request = grant_request(ids, "asha", "division")
    plan = preview(admin, request).json()
    assert plan["blockers"] == []
    assert "unit administrator" in plan["steps"][0]["summary"]
    assert rows(db_factory, ids, "asha") == []  # a preview writes nothing
    apply_reviewed(admin, request)
    (grant,) = rows(db_factory, ids, "asha")
    assert (str(grant.workspace_id), str(grant.granted_by), grant.revoked_at) == (
        ids["workspaces"]["division"],
        ids["users"]["admin"],
        None,
    )
    with db_factory() as db:
        asha = db.get(User, ids["users"]["asha"])
        assert policy.is_unit_admin(db, asha)
        events = db.scalars(select(AuditEvent).order_by(AuditEvent.id)).all()
        actions = [event.action for event in events if event.action.startswith(("people.", "unit_admin"))]
        assert sorted(actions) == ["people.change", "people.change_step", "unit_admin.grant"]
        direct = next(event for event in events if event.action == "unit_admin.grant")
        assert direct.scope_id == ids["workspaces"]["division"]
        assert direct.target_id == ids["users"]["asha"]
        assert direct.actor_id is not None and direct.reason == "Annual staff review"
    revoke = grant_request(ids, "asha", "division", "unit_admin_revoke")
    apply_reviewed(admin, revoke)
    (grant,) = rows(db_factory, ids, "asha")
    assert grant.revoked_at is not None
    with db_factory() as db:
        assert not policy.is_unit_admin(db, db.get(User, ids["users"]["asha"]))
        assert db.scalar(select(AuditEvent).where(AuditEvent.action == "unit_admin.revoke")) is not None


def test_appointment_can_be_made_again_after_withdrawal(as_user, ids, db_factory):
    admin = as_user("admin")
    request = grant_request(ids, "asha", "division")
    apply_reviewed(admin, request)
    apply_reviewed(admin, grant_request(ids, "asha", "division", "unit_admin_revoke"))
    apply_reviewed(admin, request)
    assert [row.revoked_at is None for row in rows(db_factory, ids, "asha")].count(True) == 1


@pytest.mark.parametrize(
    ("person", "unit", "code"),
    [
        ("admin", "division", "already_admin"),
        ("farhan", "division", "person_inactive"),
        ("asha", "project", "unit_unavailable"),
    ],
)
def test_appointment_blockers(as_user, ids, person, unit, code):
    plan = preview(as_user("admin"), grant_request(ids, person, unit)).json()
    assert code in [blocker["code"] for blocker in plan["blockers"]]
    confirmation = reviewed(as_user("admin"), grant_request(ids, person, unit))
    assert as_user("admin").post("/admin/changes/apply", json=confirmation).status_code == 422


def test_duplicate_appointment_and_unneeded_withdrawal_are_blocked(as_user, ids, db_factory):
    admin = as_user("admin")
    appoint(db_factory, ids, "asha", "division")
    again = preview(admin, grant_request(ids, "asha", "division")).json()
    assert [b["code"] for b in again["blockers"]] == ["no_change"]
    none = preview(admin, grant_request(ids, "bharat", "division", "unit_admin_revoke")).json()
    assert [b["code"] for b in none["blockers"]] == ["no_change"]


def test_archived_unit_does_not_give_scope(as_user, ids, db_factory):
    appoint(db_factory, ids, "asha", "section_a")
    with db_factory() as db:
        asha = db.get(User, ids["users"]["asha"])
        assert policy.people_scope(db, asha) == {ids_uuid(ids, "section_a")}
        db.execute(text("UPDATE workspaces SET archived = true WHERE name = 'Thin Films Section'"))
        db.commit()
        assert policy.people_scope(db, db.get(User, ids["users"]["asha"])) == frozenset()


def test_scope_is_the_unit_and_what_lies_below_it(ids, db_factory):
    appoint(db_factory, ids, "deepa", "division")
    appoint(db_factory, ids, "chitra", "section_b")
    with db_factory() as db:
        deepa, chitra, bharat = (db.get(User, ids["users"][name]) for name in ("deepa", "chitra", "bharat"))
        assert policy.people_scope(db, deepa) == {
            ids_uuid(ids, key) for key in ("division", "section_a", "section_b")
        }
        assert policy.people_scope(db, chitra) == {ids_uuid(ids, "section_b")}
        assert policy.people_scope(db, bharat) == frozenset()
        admin = db.get(User, ids["users"]["admin"])
        assert len(policy.people_scope(db, admin)) == 5
        assert policy.restricted_scope(db, admin) is None
        assert policy.console_sections(db, deepa) == ("people", "org")
        assert policy.console_sections(db, bharat) == ()
        deepa.is_active = False
        assert policy.people_scope(db, deepa) == frozenset()
        assert policy.console_sections(db, deepa) == ()


def test_only_one_current_appointment_per_person_and_unit(ids, db_factory):
    appoint(db_factory, ids, "asha", "division")
    with pytest.raises(IntegrityError):
        appoint(db_factory, ids, "asha", "division")


def test_migration_downgrade_refuses_to_discard_appointments(migrated):
    recreate_schema(migrated)
    config = alembic_config(migrated)
    command.upgrade(config, "head")
    engine = create_engine(migrated)
    try:
        with engine.begin() as db:
            db.execute(
                text(
                    "INSERT INTO users (id, username, display_name, is_admin, is_active, "
                    "must_set_password) VALUES "
                    "(gen_random_uuid(), 'u1', 'U One', false, true, false)"
                )
            )
            db.execute(
                text(
                    "INSERT INTO workspaces (id, kind, name, description, archived, posting_policy) "
                    "VALUES (gen_random_uuid(), 'org', 'Unit', '', false, 'open')"
                )
            )
            db.execute(
                text(
                    "INSERT INTO unit_admin_grants (id, user_id, workspace_id, granted_by) "
                    "SELECT gen_random_uuid(), u.id, w.id, u.id FROM users u, workspaces w"
                )
            )
        with pytest.raises(RuntimeError, match="appointments exist"):
            command.downgrade(config, "0035")
        with engine.begin() as db:
            db.execute(text("DELETE FROM unit_admin_grants"))
        command.downgrade(config, "0035")
    finally:
        engine.dispose()
        recreate_schema(migrated)
        command.upgrade(config, "head")
