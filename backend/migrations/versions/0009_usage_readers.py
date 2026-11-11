"""Explicit expiring operational read grants, no implicit role promotion."""

import sqlalchemy as sa
from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "usage_reader_grants",
        sa.Column("user_id", sa.UUID(), sa.ForeignKey("users.id"), primary_key=True),
        sa.Column("granted_by", sa.UUID(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("reason", sa.String(500), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )


def downgrade():
    if op.get_bind().scalar(sa.text("select count(*) from usage_reader_grants")):
        raise RuntimeError("Operational grants exist; downgrade would discard access-control state")
    op.drop_table("usage_reader_grants")
