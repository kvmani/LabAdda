"""Private bounded site measurement history, not an enforcement ledger."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "usage_observations",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("schema_version", sa.Integer(), nullable=False),
        sa.Column("payload", JSONB(), nullable=False),
        sa.Column("created_by", sa.UUID(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("schema_version = 1", name="ck_usage_observation_version"),
    )


def downgrade():
    if op.get_bind().scalar(sa.text("select count(*) from usage_observations")):
        raise RuntimeError("Usage observations exist; downgrade would discard measurement history")
    op.drop_table("usage_observations")
