"""Store voluntary membership applications and administrator approval records."""

import sqlalchemy as sa
from alembic import op

revision = "0048"
down_revision = "0047"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "join_requests",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("full_name", sa.String(120), nullable=False),
        sa.Column("username", sa.String(63), nullable=False),
        sa.Column("employee_no", sa.String(64), nullable=True),
        sa.Column("contact_email", sa.String(254), nullable=True),
        sa.Column("contact_phone", sa.String(64), nullable=True),
        sa.Column("designation", sa.String(120), nullable=True),
        sa.Column("unit_id", sa.UUID(), sa.ForeignKey("workspaces.id"), nullable=True),
        sa.Column("unit_name", sa.String(120), nullable=True),
        sa.Column("statement_of_interest", sa.Text(), nullable=True),
        sa.Column("status", sa.String(20), server_default="pending", nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reviewed_by", sa.UUID(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("review_note", sa.String(500), nullable=True),
        sa.Column("created_user_id", sa.UUID(), sa.ForeignKey("users.id"), nullable=True),
    )
    op.create_index("ix_join_requests_username", "join_requests", ["username"])
    op.create_index("ix_join_requests_employee_no", "join_requests", ["employee_no"])
    op.create_index("ix_join_requests_status", "join_requests", ["status"])
    op.create_index("ix_join_requests_created_at", "join_requests", ["created_at"])


def downgrade():
    if op.get_bind().execute(sa.text("select exists(select 1 from join_requests)")).scalar():
        raise RuntimeError("Join requests exist; downgrade would discard authority records")
    op.drop_table("join_requests")
