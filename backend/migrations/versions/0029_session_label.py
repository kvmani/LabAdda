"""Give each sign-in a public identifier and a short browser label for the sessions list."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0029"
down_revision = "0028"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("auth_sessions", sa.Column("agent_label", sa.String(length=40), nullable=True))
    op.add_column(
        "auth_sessions",
        sa.Column(
            "public_id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
    )
    op.create_index("ux_auth_sessions_public_id", "auth_sessions", ["public_id"], unique=True)


def downgrade():
    # Both columns are display metadata only; no sign-in or user content depends on them.
    op.drop_index("ux_auth_sessions_public_id", table_name="auth_sessions")
    op.drop_column("auth_sessions", "public_id")
    op.drop_column("auth_sessions", "agent_label")
