"""Owner-configurable in-app alert categories."""

from alembic import op
import sqlalchemy as sa

revision = "0025"
down_revision = "0024"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "notification_preferences",
        sa.Column("user_id", sa.UUID(), sa.ForeignKey("users.id"), primary_key=True),
        sa.Column("mentions", sa.Boolean(), nullable=False),
        sa.Column("official_notices", sa.Boolean(), nullable=False),
        sa.Column("reminders", sa.Boolean(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.CheckConstraint("revision > 0", name="ck_notification_preference_revision"),
    )


def downgrade():
    if op.get_bind().scalar(sa.text("select exists(select 1 from notification_preferences)")):
        raise RuntimeError("Notification preferences exist; downgrade would discard user choices")
    op.drop_table("notification_preferences")
