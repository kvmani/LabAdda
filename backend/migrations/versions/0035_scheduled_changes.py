"""Scheduled staff changes (PO-06): reviewed changes that take effect on a future day."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0035"
down_revision = "0034"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "scheduled_changes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("kind", sa.String(24), nullable=False),
        sa.Column("request", postgresql.JSONB, nullable=False),
        sa.Column("plan_digest", sa.String(64), nullable=False),
        sa.Column("effective_on", sa.Date, nullable=False),
        sa.Column("state", sa.String(12), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("reason", sa.Text, nullable=False),
        sa.Column("subject_id", postgresql.UUID(as_uuid=True)),
        sa.Column("steps", postgresql.JSONB, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("applied_at", sa.DateTime(timezone=True)),
        sa.Column("note", sa.Text),
        sa.CheckConstraint(
            "state in ('pending','applied','cancelled','needs_review')", name="ck_scheduled_change_state"
        ),
    )
    op.create_index(
        "ix_scheduled_changes_due",
        "scheduled_changes",
        ["effective_on"],
        postgresql_where=sa.text("state = 'pending'"),
    )
    op.create_index("ix_scheduled_changes_subject", "scheduled_changes", ["subject_id"])
    op.create_index("ix_scheduled_changes_state", "scheduled_changes", ["state"])


def downgrade():
    if op.get_bind().scalar(sa.text("select exists(select 1 from scheduled_changes)")):
        raise RuntimeError("Scheduled changes exist; downgrade would discard the record of them")
    op.drop_table("scheduled_changes")
