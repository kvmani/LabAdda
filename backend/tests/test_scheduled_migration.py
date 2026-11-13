"""Schema 0035: a downgrade refuses to discard scheduled changes."""

import pytest
from alembic import command
from sqlalchemy import create_engine, text

from labadda.cli import alembic_config
from tests.conftest import recreate_schema


def test_downgrade_refuses_while_scheduled_changes_exist(migrated):
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
                    "INSERT INTO scheduled_changes (id, kind, request, plan_digest, effective_on, "
                    "state, created_by, reason, steps) "
                    "SELECT gen_random_uuid(), 'transfer', '{}'::jsonb, repeat('a', 64), "
                    "current_date, 'pending', id, 'Test', '[]'::jsonb FROM users"
                )
            )
        with pytest.raises(RuntimeError, match="Scheduled changes exist"):
            command.downgrade(config, "0034")
        with engine.begin() as db:
            db.execute(text("DELETE FROM scheduled_changes"))
        command.downgrade(config, "0034")
    finally:
        engine.dispose()
        recreate_schema(migrated)
        command.upgrade(config, "head")
