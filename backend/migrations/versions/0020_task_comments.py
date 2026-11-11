"""Scoped immutable task discussions with durable request identity."""

from alembic import op
import sqlalchemy as sa

revision = "0020"
down_revision = "0019"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "todo_comments",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("task_id", sa.UUID(), sa.ForeignKey("todo_tasks.id"), nullable=False),
        sa.Column("author_id", sa.UUID(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("client_id", sa.UUID(), nullable=False),
        sa.Column("create_digest", sa.String(64), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("author_id", "client_id", name="uq_todo_comment_request"),
        sa.UniqueConstraint("task_id", "sequence", name="uq_todo_comment_sequence"),
        sa.CheckConstraint("sequence > 0", name="ck_todo_comment_sequence"),
    )


def downgrade():
    if op.get_bind().scalar(sa.text("select exists(select 1 from todo_comments)")):
        raise RuntimeError("Task comments exist; downgrade would discard discussion")
    op.drop_table("todo_comments")
