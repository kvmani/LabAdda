"""Retained owner-private whiteboard documents."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0037"
down_revision = "0036"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "personal_board_revisions",
        sa.Column("owner_id", sa.UUID(), sa.ForeignKey("users.id"), primary_key=True),
        sa.Column("revision", sa.Integer(), primary_key=True),
        sa.Column("objects", JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade():
    if op.get_bind().scalar(sa.text("select exists(select 1 from personal_board_revisions)")):
        raise RuntimeError("Personal whiteboard history exists; downgrade would discard private work")
    op.drop_table("personal_board_revisions")
