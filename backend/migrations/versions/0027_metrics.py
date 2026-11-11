"""Bounded metric samples and per-person activity days (AD-08)."""

import sqlalchemy as sa
from alembic import op

revision = "0027"
down_revision = "0026"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "metric_samples",
        sa.Column("bucket_start", sa.DateTime(timezone=True), primary_key=True),
        sa.Column("resolution", sa.String(8), primary_key=True),
        sa.Column("metric", sa.String(64), primary_key=True),
        sa.Column("dimension", sa.String(64), primary_key=True),
        sa.Column("value", sa.Double(), nullable=False),
        sa.Column("samples", sa.BigInteger(), nullable=False),
        sa.CheckConstraint("resolution in ('minute','hour','day')", name="ck_metric_sample_resolution"),
        sa.CheckConstraint("samples >= 0", name="ck_metric_sample_samples"),
    )
    op.create_index(
        "ix_metric_samples_series", "metric_samples", ["metric", "resolution", "dimension", "bucket_start"]
    )
    op.create_table(
        "activity_days",
        sa.Column("user_id", sa.UUID(), sa.ForeignKey("users.id"), primary_key=True),
        sa.Column("day", sa.Date(), primary_key=True),
    )
    op.create_index("ix_activity_days_day", "activity_days", ["day"])


def downgrade():
    populated = op.get_bind().scalar(
        sa.text("select exists(select 1 from metric_samples) or exists(select 1 from activity_days)")
    )
    if populated:
        raise RuntimeError("Metrics or activity days exist; downgrade would discard usage history")
    op.drop_index("ix_activity_days_day", table_name="activity_days")
    op.drop_table("activity_days")
    op.drop_index("ix_metric_samples_series", table_name="metric_samples")
    op.drop_table("metric_samples")
