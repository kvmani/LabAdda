"""Board-only touch-panel sessions and pairing codes (S3 touch, T11)

Revision ID: 0005
Revises: 0004
"""

import sqlalchemy as sa
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # A board session is bound to one workspace board; normal sessions leave this null.
    op.add_column("auth_sessions", sa.Column("workspace_id", sa.UUID(), nullable=True))
    op.add_column("auth_sessions", sa.Column("end_reason", sa.String(length=32), nullable=True))
    op.create_foreign_key(
        "fk_auth_sessions_workspace", "auth_sessions", "workspaces", ["workspace_id"], ["id"]
    )
    op.create_check_constraint(
        "ck_auth_session_kind",
        "auth_sessions",
        "(kind = 'normal' and workspace_id is null) or (kind = 'board' and workspace_id is not null)",
    )
    op.create_table(
        "panel_pairings",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("code_hash", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.UUID(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("workspace_id", sa.UUID(), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code_hash"),
    )


def downgrade() -> None:
    op.drop_table("panel_pairings")
    op.execute("UPDATE auth_sessions SET revoked_at = now() WHERE kind = 'board' AND revoked_at IS NULL")
    op.execute("DELETE FROM auth_sessions WHERE kind = 'board'")
    op.drop_constraint("ck_auth_session_kind", "auth_sessions", type_="check")
    op.drop_constraint("fk_auth_sessions_workspace", "auth_sessions", type_="foreignkey")
    op.drop_column("auth_sessions", "end_reason")
    op.drop_column("auth_sessions", "workspace_id")
