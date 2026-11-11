"""P1 populated backfill, database constraints and lossless downgrade refusal."""

import pytest
from alembic import command
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError

from labadda.cli import alembic_config
from tests.conftest import recreate_schema


@pytest.fixture
def legacy_database(migrated):
    recreate_schema(migrated)
    command.upgrade(alembic_config(migrated), "0025")
    yield migrated
    recreate_schema(migrated)
    command.upgrade(alembic_config(migrated), "head")


def test_populated_backfill_keeps_identity_and_unknown_dates(legacy_database):
    engine = create_engine(legacy_database)
    with engine.begin() as db:
        for name, active, pending in (
            ("working", True, False),
            ("pending", True, True),
            ("disabled", False, True),
        ):
            db.execute(
                text("""INSERT INTO users
                (id, username, display_name, is_admin, is_active, must_set_password)
                VALUES (gen_random_uuid(), :name, :name, false, :active, :pending)"""),
                {"name": name, "active": active, "pending": pending},
            )
    command.upgrade(alembic_config(legacy_database), "head")
    with engine.connect() as db:
        rows = db.execute(text("SELECT username, status, revision, last_seen_on, joined_on FROM users"))
        actual = {row.username: (row.status, row.revision, row.last_seen_on, row.joined_on) for row in rows}
    assert actual == {
        "working": ("active", 1, None, None),
        "pending": ("invited", 1, None, None),
        "disabled": ("left", 1, None, None),
    }
    # No novel staff information: this backfill can be reconstructed from legacy switches.
    command.downgrade(alembic_config(legacy_database), "0025")
    command.upgrade(alembic_config(legacy_database), "head")
    with engine.begin() as db:
        db.execute(
            text("UPDATE users SET employee_no='NW-100', designation='Researcher' WHERE username='working'")
        )
    with pytest.raises(RuntimeError, match="Staff records exist"):
        command.downgrade(alembic_config(legacy_database), "0025")
    with engine.connect() as db:
        assert db.scalar(text("SELECT employee_no FROM users WHERE username='working'")) == "NW-100"
    engine.dispose()


def test_staff_constraints_enforce_unique_number_valid_status_and_revision(db_factory, ids):
    with db_factory() as db:
        db.execute(text("UPDATE users SET employee_no='NW-100' WHERE id=:id"), {"id": ids["users"]["ben"]})
        db.commit()
        for statement in (
            "UPDATE users SET employee_no='NW-100' WHERE username='chen'",
            "UPDATE users SET status='invalid' WHERE username='chen'",
            "UPDATE users SET revision=0 WHERE username='chen'",
        ):
            with pytest.raises(IntegrityError), db.begin_nested():
                db.execute(text(statement))


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("last_seen_on", "2026-11-11"),
        ("joined_on", "2025-01-15"),
        ("contact_email", "staff@research.example"),
        ("revision", 2),
        ("status", "on_leave"),
    ],
)
def test_each_novel_staff_value_blocks_downgrade(db_factory, ids, settings, field, value):
    from datetime import date

    from labadda.models import User

    if field.endswith("_on"):
        value = date.fromisoformat(value)
    with db_factory() as db:
        person = db.get(User, ids["users"]["ben"])
        setattr(person, field, value)
        if field == "status" and value == "on_leave":
            person.is_active = False
        db.commit()
    with pytest.raises(RuntimeError, match="Staff records exist"):
        command.downgrade(alembic_config(settings.database_url), "0025")
    with db_factory() as db:
        assert getattr(db.get(User, ids["users"]["ben"]), field) == value
