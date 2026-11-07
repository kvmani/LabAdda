"""Migrations on real PostgreSQL: round trip, constraints, data-preserving downgrade guard."""

import pytest
import sqlalchemy
from alembic import command
from sqlalchemy import create_engine, text

from labadda.cli import alembic_config

from .conftest import recreate_schema



@pytest.fixture
def scratch_url(migrated):
    # Runs against the test database, then restores head for later tests.
    yield migrated
    recreate_schema(migrated)
    command.upgrade(alembic_config(migrated), "head")


def test_round_trip_and_group_guard(scratch_url):
    cfg = alembic_config(scratch_url)
    recreate_schema(scratch_url)
    command.upgrade(cfg, "head")
    command.downgrade(cfg, "base")  # empty database: full downgrade succeeds
    command.upgrade(cfg, "0002")
    engine = create_engine(scratch_url)
    with engine.begin() as conn:
        with pytest.raises(sqlalchemy.exc.IntegrityError):
            with conn.begin_nested():
                conn.execute(text("insert into workspaces (id, kind, name, description, archived, posting_policy)"
                                  " values (gen_random_uuid(), 'group', 'g', '', false, 'open')"))
    command.upgrade(cfg, "head")
    with engine.begin() as conn:
        conn.execute(text("insert into workspaces (id, kind, name, description, archived, posting_policy)"
                          " values (gen_random_uuid(), 'group', 'Kept group', '', false, 'open')"))
    with pytest.raises(Exception, match="collaborative groups exist"):
        command.downgrade(cfg, "0002")
    with engine.connect() as conn:
        assert conn.execute(text("select count(*) from workspaces where name = 'Kept group'")).scalar() == 1
        assert conn.execute(text("select version_num from alembic_version")).scalar() == "0003"
    engine.dispose()


def test_single_root_and_flat_spaces(db_factory, ids):
    with db_factory() as db:
        with pytest.raises(sqlalchemy.exc.IntegrityError):
            db.execute(text("insert into workspaces (id, kind, name, description, archived, posting_policy)"
                            " values (gen_random_uuid(), 'org', 'Second root', '', false, 'open')"))
        db.rollback()
        with pytest.raises(sqlalchemy.exc.IntegrityError):
            db.execute(text("insert into workspaces (id, kind, name, description, parent_id, archived, posting_policy)"
                            " values (gen_random_uuid(), 'group', 'g', '', :p, false, 'open')"),
                       {"p": ids["workspaces"]["root"]})
        db.rollback()
