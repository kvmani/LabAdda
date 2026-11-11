"""Content: noticeboard, assets, notes, notifications, chat, boards

Revision ID: 0002
Revises: 0001
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "posts",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("seq", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("workspace_id", sa.UUID(), nullable=False),
        sa.Column("author_id", sa.UUID(), nullable=False),
        sa.Column("parent_id", sa.UUID(), nullable=True),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("pinned", sa.Boolean(), nullable=False),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("remind_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reminder_processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("client_id", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("edited_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("removed_by", sa.UUID(), nullable=True),
        sa.Column("removed_reason", sa.Text(), nullable=True),
        sa.CheckConstraint("kind in ('discussion','official')", name="ck_post_kind"),
        sa.ForeignKeyConstraint(
            ["author_id"],
            ["users.id"],
        ),
        sa.ForeignKeyConstraint(
            ["parent_id"],
            ["posts.id"],
        ),
        sa.ForeignKeyConstraint(
            ["removed_by"],
            ["users.id"],
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("author_id", "client_id", name="uq_post_client_id"),
        sa.UniqueConstraint("seq"),
    )
    op.create_index("ix_posts_parent", "posts", ["parent_id"], unique=False)
    op.create_index(
        "ix_posts_pending_reminder",
        "posts",
        ["remind_at"],
        unique=False,
        postgresql_where=sa.text("reminder_processed_at is null"),
    )
    op.create_index("ix_posts_workspace_seq", "posts", ["workspace_id", "seq"], unique=False)
    op.create_table(
        "assets",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("owner_id", sa.UUID(), nullable=False),
        sa.Column("storage_key", sa.String(length=80), nullable=False),
        sa.Column("display_name", sa.String(length=200), nullable=False),
        sa.Column("media_type", sa.String(length=64), nullable=False),
        sa.Column("size", sa.BigInteger(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("post_id", sa.UUID(), nullable=True),
        sa.Column("has_preview", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("status = 'provisional' or post_id is not null", name="ck_asset_committed_owner"),
        sa.CheckConstraint("status in ('provisional','committed')", name="ck_asset_status"),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["users.id"],
        ),
        sa.ForeignKeyConstraint(
            ["post_id"],
            ["posts.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("storage_key"),
    )
    op.create_index("ix_assets_post", "assets", ["post_id"], unique=False)

    op.create_table(
        "notes",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("owner_id", sa.UUID(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("remind_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reminder_processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["users.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_notes_owner", "notes", ["owner_id"], unique=False)
    op.create_table(
        "notifications",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("recipient_id", sa.UUID(), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("workspace_id", sa.UUID(), nullable=True),
        sa.Column("source_type", sa.String(length=16), nullable=False),
        sa.Column("source_id", sa.UUID(), nullable=False),
        sa.Column("dedupe_key", sa.String(length=200), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["recipient_id"],
            ["users.id"],
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("dedupe_key"),
    )
    op.create_index(
        "ix_notifications_recipient", "notifications", ["recipient_id", "created_at"], unique=False
    )
    op.create_table(
        "chat_messages",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("seq", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("workspace_id", sa.UUID(), nullable=False),
        sa.Column("author_id", sa.UUID(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("client_id", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["author_id"],
            ["users.id"],
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("author_id", "client_id", name="uq_chat_client_id"),
        sa.UniqueConstraint("seq"),
    )
    op.create_index("ix_chat_workspace_seq", "chat_messages", ["workspace_id", "seq"], unique=False)
    op.create_table(
        "chat_reads",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("workspace_id", sa.UUID(), nullable=False),
        sa.Column("last_seq", sa.BigInteger(), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
        ),
        sa.PrimaryKeyConstraint("user_id", "workspace_id"),
    )
    op.create_table(
        "boards",
        sa.Column("workspace_id", sa.UUID(), nullable=False),
        sa.Column("epoch", sa.Integer(), nullable=False),
        sa.Column("revision", sa.BigInteger(), nullable=False),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
        ),
        sa.PrimaryKeyConstraint("workspace_id"),
    )
    op.create_table(
        "board_ops",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("workspace_id", sa.UUID(), nullable=False),
        sa.Column("epoch", sa.Integer(), nullable=False),
        sa.Column("revision", sa.BigInteger(), nullable=False),
        sa.Column("op_id", sa.String(length=64), nullable=False),
        sa.Column("actor_id", sa.UUID(), nullable=False),
        sa.Column("op_type", sa.String(length=16), nullable=False),
        sa.Column("object_id", sa.String(length=64), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("payload_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("op_type in ('add','erase','undo','move')", name="ck_board_op_type"),
        sa.ForeignKeyConstraint(
            ["actor_id"],
            ["users.id"],
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("workspace_id", "epoch", "actor_id", "op_id", name="uq_board_op_identity"),
        sa.UniqueConstraint("workspace_id", "revision", name="uq_board_op_revision"),
    )


def downgrade() -> None:
    op.drop_table("board_ops")
    op.drop_table("boards")
    op.drop_table("chat_reads")
    op.drop_table("chat_messages")
    op.drop_table("notifications")
    op.drop_table("notes")
    op.drop_table("assets")
    op.drop_table("posts")
