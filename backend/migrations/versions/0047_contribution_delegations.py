"""Keep revocable child-to-parent contribution delegations and their history."""

import sqlalchemy as sa
from alembic import op

revision = "0047"
down_revision = "0046"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "contribution_delegations",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("source_id", sa.UUID(), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("destination_id", sa.UUID(), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("user_id", sa.UUID(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("granted_by", sa.UUID(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.Column("revision", sa.Integer(), server_default="1", nullable=False),
    )
    for field in ("source_id", "destination_id", "user_id"):
        op.create_index(f"ix_contribution_delegations_{field}", "contribution_delegations", [field])


def downgrade():
    if op.get_bind().execute(sa.text("select exists(select 1 from contribution_delegations)")).scalar():
        raise RuntimeError("Delegation history exists; downgrade would discard authority records")
    op.drop_table("contribution_delegations")
