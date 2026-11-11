"""Operational events raised by health state changes (AD-06)."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0030"
down_revision = "0029"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "ops_events",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("code", sa.String(64), nullable=False),
        sa.Column("component", sa.String(32), nullable=False),
        sa.Column("severity", sa.String(8), nullable=False),
        sa.Column("summary", sa.String(240), nullable=False),
        sa.Column("detail", postgresql.JSONB(), nullable=False),
        sa.Column("first_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("count", sa.Integer(), nullable=False),
        sa.Column("state", sa.String(12), nullable=False),
        sa.Column("acknowledged_by", sa.UUID(), sa.ForeignKey("users.id")),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True)),
        sa.Column("note", sa.Text()),
        sa.Column("resolved_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint("severity in ('info','warning','error','critical')", name="ck_ops_event_severity"),
        sa.CheckConstraint("state in ('open','acknowledged','resolved')", name="ck_ops_event_state"),
        sa.CheckConstraint("count >= 1", name="ck_ops_event_count"),
    )
    op.create_index("ix_ops_events_last", "ops_events", ["last_at", "id"])
    op.create_index("ix_ops_events_state", "ops_events", ["state", "last_at"])
    op.create_index(
        "uq_ops_events_live",
        "ops_events",
        ["code", "component"],
        unique=True,
        postgresql_where=sa.text("state <> 'resolved'"),
    )


def downgrade():
    if op.get_bind().scalar(sa.text("select exists(select 1 from ops_events)")):
        raise RuntimeError("Operational events exist; downgrade would discard the event history")
    op.drop_index("uq_ops_events_live", table_name="ops_events")
    op.drop_index("ix_ops_events_state", table_name="ops_events")
    op.drop_index("ix_ops_events_last", table_name="ops_events")
    op.drop_table("ops_events")
