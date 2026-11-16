"""Retain cancelled calendar events and require revisioned edits."""

import sqlalchemy as sa
from alembic import op

revision = "0043"
down_revision = "0042"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("calendar_events", sa.Column("revision", sa.Integer(), nullable=False, server_default="1"))
    op.add_column("calendar_events", sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True))


def downgrade():
    if op.get_bind().execute(sa.text("select exists(select 1 from calendar_events)")).scalar():
        raise RuntimeError("Calendar events exist; downgrade would discard revision and cancellation history")
    op.drop_column("calendar_events", "cancelled_at")
    op.drop_column("calendar_events", "revision")
