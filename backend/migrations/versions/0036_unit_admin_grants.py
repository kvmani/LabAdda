"""Unit administrators (PO-24): who may administer people and units of one branch."""

import sqlalchemy as sa
from alembic import op

revision = "0036"
down_revision = "0035"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "unit_admin_grants",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("user_id", sa.UUID(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("workspace_id", sa.UUID(), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("granted_by", sa.UUID(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("granted_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
    )
    op.create_index(
        "uq_unit_admin_grants_current",
        "unit_admin_grants",
        ["user_id", "workspace_id"],
        unique=True,
        postgresql_where=sa.text("revoked_at IS NULL"),
    )
    op.create_index("ix_unit_admin_grants_workspace", "unit_admin_grants", ["workspace_id"])


def downgrade():
    if op.get_bind().scalar(sa.text("select exists(select 1 from unit_admin_grants)")):
        raise RuntimeError(
            "Unit administrator appointments exist; downgrade would discard the record of them"
        )
    op.drop_index("ix_unit_admin_grants_workspace", table_name="unit_admin_grants")
    op.drop_index("uq_unit_admin_grants_current", table_name="unit_admin_grants")
    op.drop_table("unit_admin_grants")
