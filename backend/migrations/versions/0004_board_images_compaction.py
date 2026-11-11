"""Board images, compacted board history, snapshot provenance

Revision ID: 0004
Revises: 0003
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Images embedded on a board are owned by that workspace's board.
    op.add_column("assets", sa.Column("board_workspace_id", sa.UUID(), nullable=True))
    op.create_foreign_key("fk_assets_board_workspace", "assets", "workspaces", ["board_workspace_id"], ["id"])
    op.drop_constraint("ck_asset_committed_owner", "assets", type_="check")
    op.create_check_constraint(
        "ck_asset_committed_owner",
        "assets",
        "status = 'provisional' or post_id is not null or board_workspace_id is not null",
    )
    op.create_check_constraint(
        "ck_asset_single_owner", "assets", "post_id is null or board_workspace_id is null"
    )
    op.create_index("ix_assets_board", "assets", ["board_workspace_id"])

    # Operations at or below base_revision were folded into board_snapshots and removed.
    op.add_column("boards", sa.Column("base_revision", sa.BigInteger(), nullable=False, server_default="0"))
    op.create_table(
        "board_snapshots",
        sa.Column("workspace_id", sa.UUID(), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("epoch", sa.Integer(), nullable=False),
        sa.Column("revision", sa.BigInteger(), nullable=False),
        sa.Column("state", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("workspace_id", "epoch", "revision"),
    )

    # Published board snapshots: provenance of the destination-owned copy.
    op.add_column("posts", sa.Column("source_workspace_id", sa.UUID(), nullable=True))
    op.add_column("posts", sa.Column("source_revision", sa.BigInteger(), nullable=True))
    op.create_foreign_key("fk_posts_source_workspace", "posts", "workspaces", ["source_workspace_id"], ["id"])


def downgrade() -> None:
    op.execute(
        "DO $$ BEGIN IF EXISTS (SELECT 1 FROM assets WHERE board_workspace_id IS NOT NULL) "
        "OR EXISTS (SELECT 1 FROM board_snapshots) THEN "
        "RAISE EXCEPTION 'board images or compacted history exist; downgrade would lose data'; END IF; END $$;"
    )
    op.drop_constraint("fk_posts_source_workspace", "posts", type_="foreignkey")
    op.drop_column("posts", "source_revision")
    op.drop_column("posts", "source_workspace_id")
    op.drop_table("board_snapshots")
    op.drop_column("boards", "base_revision")
    op.drop_index("ix_assets_board", table_name="assets")
    op.drop_constraint("ck_asset_single_owner", "assets", type_="check")
    op.drop_constraint("ck_asset_committed_owner", "assets", type_="check")
    op.create_check_constraint(
        "ck_asset_committed_owner", "assets", "status = 'provisional' or post_id is not null"
    )
    op.drop_constraint("fk_assets_board_workspace", "assets", type_="foreignkey")
    op.drop_column("assets", "board_workspace_id")
