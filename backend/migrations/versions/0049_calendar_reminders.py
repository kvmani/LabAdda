"""Remember processed calendar start times without replaying muted occurrences."""

import sqlalchemy as sa
from alembic import op

revision = "0049"
down_revision = "0048"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("calendar_events", sa.Column("reminder_start_processed_at", sa.DateTime(timezone=True)))


def downgrade():
    count = (
        op.get_bind()
        .execute(
            sa.text("SELECT count(*) FROM calendar_events WHERE reminder_start_processed_at IS NOT NULL")
        )
        .scalar_one()
    )
    if count:
        raise RuntimeError("Cannot discard processed calendar reminders.")
    op.drop_column("calendar_events", "reminder_start_processed_at")
