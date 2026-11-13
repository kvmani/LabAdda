"""Schema 0034: unit codes are backfilled uniquely and a downgrade refuses to discard them."""

import pytest
from alembic import command
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError

from labadda.cli import alembic_config
from tests.conftest import recreate_schema

UNIT = text(
    "INSERT INTO workspaces (id, kind, name, description, archived, posting_policy) "
    "VALUES (gen_random_uuid(), :kind, :name, '', false, 'open')"
)


def test_codes_backfill_uniquely_and_downgrade_is_guarded(migrated):
    recreate_schema(migrated)
    config = alembic_config(migrated)
    command.upgrade(config, "0033")
    engine = create_engine(migrated)
    try:
        with engine.begin() as db:
            db.execute(UNIT, {"kind": "org", "name": "Structural Studies"})
            db.execute(
                text(
                    "INSERT INTO workspaces "
                    "(id, kind, name, description, archived, posting_policy, parent_id) "
                    "SELECT gen_random_uuid(), 'org', 'Spectroscopy Services', '', false, 'open', id "
                    "FROM workspaces WHERE name = 'Structural Studies'"
                )
            )
            db.execute(UNIT, {"kind": "project", "name": "Project Tejas"})
        command.upgrade(config, "head")
        with engine.begin() as db:
            rows = db.execute(text("SELECT kind, code FROM workspaces ORDER BY name")).all()
            assert sorted(code for kind, code in rows if kind == "org") == ["SS", "SS-2"]
            assert [code for kind, code in rows if kind == "project"] == [None]
        for bad in ("ss", "S", "SS_1"):
            with pytest.raises(IntegrityError), engine.begin() as db:
                db.execute(text("UPDATE workspaces SET code = :c WHERE name = 'Project Tejas'"), {"c": bad})
        with pytest.raises(IntegrityError), engine.begin() as db:
            db.execute(text("UPDATE workspaces SET code = 'SS' WHERE code = 'SS-2'"))
        with engine.begin() as db:
            db.execute(text("UPDATE workspaces SET code = 'CHOSEN-1' WHERE code = 'SS-2'"))
        with pytest.raises(RuntimeError, match="Chosen unit codes exist"):
            command.downgrade(config, "0033")
        with engine.begin() as db:
            db.execute(text("UPDATE workspaces SET code = 'SS-2' WHERE code = 'CHOSEN-1'"))
        command.downgrade(config, "0033")  # regenerated codes are not data worth refusing for
    finally:
        engine.dispose()
        recreate_schema(migrated)
        command.upgrade(config, "head")
