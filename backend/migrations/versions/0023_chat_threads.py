"""One-level workspace chat threads with legacy stream compatibility."""

import sqlalchemy as sa
from alembic import op

revision = "0023"
down_revision = "0022"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("chat_messages", sa.Column("parent_id", sa.UUID(), sa.ForeignKey("chat_messages.id")))
    op.create_check_constraint("ck_chat_not_self", "chat_messages", "parent_id is null or parent_id <> id")
    op.create_index("ix_chat_parent_seq", "chat_messages", ["parent_id", "seq"])


def downgrade():
    if op.get_bind().scalar(
        sa.text("select exists(select 1 from chat_messages where parent_id is not null)")
    ):
        raise RuntimeError("Chat replies exist; downgrade would discard thread context")
    op.drop_index("ix_chat_parent_seq", table_name="chat_messages")
    op.drop_constraint("ck_chat_not_self", "chat_messages", type_="check")
    op.drop_column("chat_messages", "parent_id")
