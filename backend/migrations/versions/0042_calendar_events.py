"""Calendar events for site, workspace, and personal scopes."""

import sqlalchemy as sa
from alembic import op

revision = "0042"
down_revision = "0041"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "calendar_events",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("scope_kind", sa.String(32), nullable=False),
        sa.Column(
            "workspace_id", sa.UUID(), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=True
        ),
        sa.Column("owner_id", sa.UUID(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=True),
        sa.Column("created_by", sa.UUID(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("title", sa.String(140), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("location", sa.String(140), nullable=True),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("all_day", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("color", sa.String(32), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "scope_kind IN ('site', 'workspace', 'personal')", name="ck_calendar_events_scope"
        ),
        sa.CheckConstraint("starts_at <= ends_at", name="ck_calendar_events_dates"),
    )

    op.create_index("ix_calendar_events_time", "calendar_events", ["starts_at", "ends_at"])
    op.create_index("ix_calendar_events_workspace", "calendar_events", ["workspace_id", "starts_at"])
    op.create_index("ix_calendar_events_owner", "calendar_events", ["owner_id", "starts_at"])
    op.create_index("ix_calendar_events_scope", "calendar_events", ["scope_kind", "starts_at"])


def downgrade():
    bind = op.get_bind()
    has_events = bind.execute(sa.text("SELECT EXISTS (SELECT 1 FROM calendar_events)")).scalar()
    if has_events:
        raise RuntimeError("Calendar events exist; downgrade would discard them")
    op.drop_table("calendar_events")
