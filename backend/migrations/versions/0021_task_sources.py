"""Protected conversation references for tasks."""

from alembic import op
import sqlalchemy as sa

revision = "0021"
down_revision = "0020"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "todo_sources",
        sa.Column("task_id", sa.UUID(), sa.ForeignKey("todo_tasks.id"), primary_key=True),
        sa.Column("post_id", sa.UUID(), sa.ForeignKey("posts.id", ondelete="SET NULL")),
        sa.Column("chat_message_id", sa.UUID(), sa.ForeignKey("chat_messages.id", ondelete="SET NULL")),
        sa.CheckConstraint("post_id is null or chat_message_id is null", name="ck_todo_source_kind"),
    )


def downgrade():
    if op.get_bind().scalar(sa.text("select exists(select 1 from todo_sources)")):
        raise RuntimeError("Task sources exist; downgrade would discard protected references")
    op.drop_table("todo_sources")
