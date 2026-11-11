"""Bind validated stored assets to one chat destination."""

from alembic import op
import sqlalchemy as sa

revision = "0024"
down_revision = "0023"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("assets", sa.Column("chat_message_id", sa.UUID(), sa.ForeignKey("chat_messages.id")))
    op.create_index("ix_assets_chat", "assets", ["chat_message_id"])
    op.drop_constraint("ck_asset_committed_owner", "assets", type_="check")
    op.drop_constraint("ck_asset_single_owner", "assets", type_="check")
    op.create_check_constraint(
        "ck_asset_committed_owner",
        "assets",
        "status = 'provisional' or post_id is not null or board_workspace_id is not null or chat_message_id is not null",
    )
    op.create_check_constraint(
        "ck_asset_single_owner", "assets", "num_nonnulls(post_id, board_workspace_id, chat_message_id) <= 1"
    )


def downgrade():
    if op.get_bind().scalar(sa.text("select exists(select 1 from assets where chat_message_id is not null)")):
        raise RuntimeError("Chat attachments exist; downgrade would discard file destination")
    op.drop_constraint("ck_asset_single_owner", "assets", type_="check")
    op.drop_constraint("ck_asset_committed_owner", "assets", type_="check")
    op.drop_index("ix_assets_chat", table_name="assets")
    op.drop_column("assets", "chat_message_id")
    op.create_check_constraint(
        "ck_asset_committed_owner",
        "assets",
        "status = 'provisional' or post_id is not null or board_workspace_id is not null",
    )
    op.create_check_constraint(
        "ck_asset_single_owner", "assets", "post_id is null or board_workspace_id is null"
    )
