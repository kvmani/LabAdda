"""Staff import (P6x): contact fields, a forced password change, and the level of an organisation unit."""

import sqlalchemy as sa
from alembic import op

revision = "0038"
down_revision = "0037"
branch_labels = None
depends_on = None

LEVELS = "'organisation','group','division','section'"


def upgrade():
    op.add_column("users", sa.Column("extension", sa.String(32)))
    op.add_column("users", sa.Column("residence_phone", sa.String(64)))
    op.add_column(
        "users",
        sa.Column("must_change_password", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column("workspaces", sa.Column("level", sa.String(16)))
    op.create_check_constraint(
        "ck_workspace_level", "workspaces", f"level is null or (kind = 'org' and level in ({LEVELS}))"
    )


def downgrade():
    bind = op.get_bind()
    held = bind.scalar(
        sa.text(
            "select exists(select 1 from users where extension is not null "
            "or residence_phone is not null or must_change_password) "
            "or exists(select 1 from workspaces where level is not null)"
        )
    )
    if held:
        raise RuntimeError(
            "Extensions, residence phones, pending password changes or unit levels exist; "
            "downgrade would discard them"
        )
    op.drop_constraint("ck_workspace_level", "workspaces", type_="check")
    op.drop_column("workspaces", "level")
    op.drop_column("users", "must_change_password")
    op.drop_column("users", "residence_phone")
    op.drop_column("users", "extension")
