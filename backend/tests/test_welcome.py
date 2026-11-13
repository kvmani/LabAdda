"""H4: first-sign-in welcome and what's-new state stored per person."""

import pytest
from alembic import command
from sqlalchemy import create_engine, text

from labadda import __version__
from labadda.cli import alembic_config
from labadda.models import User
from tests.conftest import recreate_schema
from tests.test_panel import pair


def stored(db_factory, username):
    with db_factory() as db:
        user = db.query(User).filter_by(username=username).one()
        return user.welcome_dismissed_at, user.whats_new_seen_release


@pytest.fixture
def newcomer(as_user, db_factory):
    """Bharat as a person who has not seen the welcome yet."""
    with db_factory() as db:
        user = db.query(User).filter_by(username="bharat").one()
        user.welcome_dismissed_at = None
        user.whats_new_seen_release = None
        db.commit()
    return as_user("bharat")


def test_fixture_people_start_welcomed(as_user):
    body = as_user("bharat").get("/auth/session").json()
    assert body["welcome_pending"] is False
    assert body["whats_new_pending"] is False
    assert body["release"] == __version__


def test_new_person_sees_the_welcome_until_dismissed(newcomer, db_factory):
    body = newcomer.get("/auth/session").json()
    assert body["welcome_pending"] is True
    assert body["whats_new_pending"] is False
    assert newcomer.post("/me/welcome/dismiss").json() == {"ok": True}
    after = newcomer.get("/auth/session").json()
    assert after["welcome_pending"] is False
    assert after["whats_new_pending"] is False
    assert stored(db_factory, "bharat")[1] == __version__
    assert newcomer.post("/me/welcome/dismiss").status_code == 200


def test_whats_new_shows_once_per_release(as_user, db_factory):
    with db_factory() as db:
        db.query(User).filter_by(username="bharat").one().whats_new_seen_release = "0.0.1"
        db.commit()
    api = as_user("bharat")
    assert api.get("/auth/session").json()["whats_new_pending"] is True
    assert api.post("/me/whats-new/seen").json() == {"ok": True}
    assert api.get("/auth/session").json()["whats_new_pending"] is False


def test_state_is_per_person(newcomer, as_user):
    newcomer.post("/me/welcome/dismiss")
    assert as_user("asha").get("/auth/session").json()["welcome_pending"] is False


def test_denial_matrix(make_client, as_user, ids, newcomer, db_factory):
    anon = make_client()
    assert anon.post("/me/welcome/dismiss").status_code == 401
    assert anon.post("/me/whats-new/seen").status_code == 401
    kiosk = pair(as_user, make_client, ids)
    assert kiosk.post("/me/welcome/dismiss").status_code == 401
    assert kiosk.post("/me/whats-new/seen").status_code == 401
    assert stored(db_factory, "bharat")[0] is None


def test_dismissal_needs_the_security_token(newcomer):
    newcomer.csrf = "wrong"
    assert newcomer.post("/me/welcome/dismiss").status_code == 403


def test_deactivated_person_cannot_dismiss(as_user, newcomer, db_factory):
    with db_factory() as db:
        db.query(User).filter_by(username="bharat").one().is_active = False
        db.commit()
    assert newcomer.post("/me/welcome/dismiss").status_code == 401


def test_migration_adds_empty_columns_and_downgrades(migrated):
    recreate_schema(migrated)
    config = alembic_config(migrated)
    command.upgrade(config, "0031")
    engine = create_engine(migrated)
    with engine.begin() as db:
        db.execute(
            text("""INSERT INTO users (id, username, display_name, is_admin, is_active, must_set_password)
                VALUES (gen_random_uuid(), 'kept', 'Kept', false, true, false)""")
        )
    command.upgrade(config, "head")
    with engine.connect() as db:
        row = db.execute(text("SELECT welcome_dismissed_at, whats_new_seen_release FROM users")).one()
    assert tuple(row) == (None, None)
    command.downgrade(config, "0031")
    with engine.connect() as db:
        assert db.execute(text("SELECT username FROM users")).scalar() == "kept"
    command.upgrade(config, "head")
    recreate_schema(migrated)
    command.upgrade(config, "head")
