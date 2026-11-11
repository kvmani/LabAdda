"""Collaborative groups: user-created flat workspaces with direct grants (S2.1)

Revision ID: 0003
Revises: 0002
"""

from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("ck_workspace_kind", "workspaces", type_="check")
    op.create_check_constraint("ck_workspace_kind", "workspaces", "kind in ('org','project','group')")
    op.create_index("ix_workspaces_kind_created_by", "workspaces", ["kind", "created_by"])


def downgrade() -> None:
    # Refuse to silently drop user data: downgrade only when no group exists.
    op.execute(
        "DO $$ BEGIN IF EXISTS (SELECT 1 FROM workspaces WHERE kind = 'group') THEN "
        "RAISE EXCEPTION 'collaborative groups exist; archive and export before downgrading'; END IF; END $$;"
    )
    op.drop_index("ix_workspaces_kind_created_by", table_name="workspaces")
    op.drop_constraint("ck_workspace_kind", "workspaces", type_="check")
    op.create_check_constraint("ck_workspace_kind", "workspaces", "kind in ('org','project')")
