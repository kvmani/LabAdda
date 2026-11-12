"""Schema 0033: unit positions upgrade empty and refuse a downgrade that would lose them."""

import pytest
from alembic import command
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError

from labadda.cli import alembic_config
from tests.conftest import recreate_schema

INSERT = text("""
    INSERT INTO unit_positions (id, workspace_id, user_id, position, starts_on, acting, ends_on, revert_role)
    VALUES (gen_random_uuid(), :unit, :person, :position, DATE '2026-01-05', :acting, :ends, :revert)
""")


def test_positions_upgrade_guarded_downgrade_and_constraints(migrated):
    recreate_schema(migrated)
    config = alembic_config(migrated)
    command.upgrade(config, "0032")
    command.upgrade(config, "head")
    engine = create_engine(migrated)
    try:
        with engine.begin() as db:
            unit = db.execute(
                text(
                    "INSERT INTO workspaces (id, kind, name, description, archived, posting_policy) "
                    "VALUES (gen_random_uuid(), 'org', 'Unit', '', false, 'open') RETURNING id"
                )
            ).scalar()
            person = db.execute(
                text("""INSERT INTO users (id, username, display_name, is_admin, is_active, must_set_password)
                    VALUES (gen_random_uuid(), 'holder', 'Holder', false, true, false) RETURNING id""")
            ).scalar()
            values = {
                "unit": unit,
                "person": person,
                "position": "head",
                "acting": False,
                "ends": None,
                "revert": None,
            }
            db.execute(INSERT, values)
        for bad in (
            {"position": "chief"},
            {"acting": True},
            {"position": "charge", "acting": True, "ends": "2026-02-01"},
            {"ends": "2026-01-01"},
            {"revert": "owner"},
        ):
            with pytest.raises(IntegrityError), engine.begin() as db:
                db.execute(INSERT, {**values, "position": "deputy", **bad})
        with pytest.raises(IntegrityError), engine.begin() as db:
            db.execute(INSERT, values)
        with pytest.raises(RuntimeError, match="Unit positions exist"):
            command.downgrade(config, "0032")
        with engine.begin() as db:
            assert db.execute(text("SELECT count(*) FROM unit_positions")).scalar() == 1
            db.execute(text("DELETE FROM unit_positions"))
        command.downgrade(config, "0032")
        with engine.connect() as db:
            assert db.execute(text("SELECT to_regclass('unit_positions')")).scalar() is None
    finally:
        engine.dispose()
        recreate_schema(migrated)
        command.upgrade(config, "head")
