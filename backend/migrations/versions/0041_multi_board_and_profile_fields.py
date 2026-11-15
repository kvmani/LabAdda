"""Multi-board support (tabbed whiteboards per scope), system settings, and user profile fields."""

import sqlalchemy as sa
from alembic import op

revision = "0041"
down_revision = "0040"
branch_labels = None
depends_on = None


def upgrade():
    # 1. system_settings
    op.create_table(
        "system_settings",
        sa.Column("key", sa.String(64), primary_key=True),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column("description", sa.String(255), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_by", sa.UUID(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
    )
    op.execute(
        "INSERT INTO system_settings (key, value, description) VALUES "
        "('max_whiteboards_per_scope', '5', 'Maximum number of whiteboards allowed per scope/workspace')"
    )

    # 2. user profile fields
    op.add_column("users", sa.Column("mobile", sa.String(64), nullable=True))
    op.add_column("users", sa.Column("alternate_email", sa.String(254), nullable=True))
    op.add_column("users", sa.Column("specialization", sa.Text(), nullable=True))
    op.add_column("users", sa.Column("avatar_data", sa.Text(), nullable=True))

    # 3. boards (title for default board_index=0)
    op.add_column("boards", sa.Column("title", sa.String(64), nullable=False, server_default="Board 1"))

    # 4. workspace_boards (for secondary boards board_index >= 1)
    op.create_table(
        "workspace_boards",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("workspace_id", sa.UUID(), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
        sa.Column("board_index", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(64), nullable=False, server_default="Board 2"),
        sa.Column("epoch", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("revision", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("base_revision", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("charges_epoch", sa.Integer(), nullable=True),
        sa.UniqueConstraint("workspace_id", "board_index", name="uq_workspace_boards_index"),
    )

    # 5. board_ops
    op.add_column("board_ops", sa.Column("board_index", sa.Integer(), nullable=False, server_default="0"))
    op.drop_constraint("uq_board_op_identity", "board_ops", type_="unique")
    op.drop_constraint("uq_board_op_revision", "board_ops", type_="unique")
    op.create_unique_constraint(
        "uq_board_op_identity",
        "board_ops",
        ["workspace_id", "board_index", "epoch", "actor_id", "op_id"],
    )
    op.create_unique_constraint(
        "uq_board_op_revision",
        "board_ops",
        ["workspace_id", "board_index", "revision"],
    )

    # 6. board_snapshots
    op.add_column("board_snapshots", sa.Column("board_index", sa.Integer(), nullable=False, server_default="0"))
    op.drop_constraint("board_snapshots_pkey", "board_snapshots", type_="primary")
    op.create_primary_key(
        "board_snapshots_pkey", "board_snapshots", ["workspace_id", "board_index", "epoch", "revision"]
    )

    # 7. personal_board_revisions
    op.add_column("personal_board_revisions", sa.Column("board_index", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("personal_board_revisions", sa.Column("title", sa.String(64), nullable=False, server_default="Board 1"))
    op.drop_constraint("personal_board_revisions_pkey", "personal_board_revisions", type_="primary")
    op.create_primary_key(
        "personal_board_revisions_pkey", "personal_board_revisions", ["owner_id", "board_index", "revision"]
    )


def downgrade():
    bind = op.get_bind()
    has_extra_boards = bind.scalar(
        sa.text(
            "SELECT EXISTS("
            "  SELECT 1 FROM workspace_boards "
            "  UNION ALL "
            "  SELECT 1 FROM board_ops WHERE board_index > 0 "
            "  UNION ALL "
            "  SELECT 1 FROM personal_board_revisions WHERE board_index > 0"
            ")"
        )
    )
    if has_extra_boards:
        raise RuntimeError("Multiple whiteboards exist; downgrade would discard secondary boards")

    # Revert personal_board_revisions
    op.drop_constraint("personal_board_revisions_pkey", "personal_board_revisions", type_="primary")
    op.create_primary_key("personal_board_revisions_pkey", "personal_board_revisions", ["owner_id", "revision"])
    op.drop_column("personal_board_revisions", "title")
    op.drop_column("personal_board_revisions", "board_index")

    # Revert board_snapshots
    op.drop_constraint("board_snapshots_pkey", "board_snapshots", type_="primary")
    op.create_primary_key("board_snapshots_pkey", "board_snapshots", ["workspace_id", "epoch", "revision"])
    op.drop_column("board_snapshots", "board_index")

    # Revert board_ops
    op.drop_constraint("uq_board_op_revision", "board_ops", type_="unique")
    op.drop_constraint("uq_board_op_identity", "board_ops", type_="unique")
    op.create_unique_constraint("uq_board_op_identity", "board_ops", ["workspace_id", "epoch", "actor_id", "op_id"])
    op.create_unique_constraint("uq_board_op_revision", "board_ops", ["workspace_id", "revision"])
    op.drop_column("board_ops", "board_index")

    # Revert workspace_boards
    op.drop_table("workspace_boards")

    # Revert boards
    op.drop_column("boards", "title")

    # Revert users
    op.drop_column("users", "avatar_data")
    op.drop_column("users", "specialization")
    op.drop_column("users", "alternate_email")
    op.drop_column("users", "mobile")

    # Revert system_settings
    op.drop_table("system_settings")
