"""Remember per person whether the welcome was dismissed and which release notes were seen (H4)."""

import sqlalchemy as sa
from alembic import op

revision = "0032"
down_revision = "0031"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("users", sa.Column("welcome_dismissed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("users", sa.Column("whats_new_seen_release", sa.String(length=32), nullable=True))


def downgrade():
    # Both columns only decide whether a hint is shown again; no user content depends on them.
    op.drop_column("users", "whats_new_seen_release")
    op.drop_column("users", "welcome_dismissed_at")
