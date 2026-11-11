"""Task workflow states and scoped change history."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "0018"
down_revision = "0017"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("todo_tasks", sa.Column("status", sa.String(16), nullable=False, server_default="todo"))
    op.execute("update todo_tasks set status=case when done then 'done' else 'todo' end")
    op.create_check_constraint(
        "ck_todo_task_status",
        "todo_tasks",
        "status in ('todo','in_progress','blocked','done') and done = (status = 'done')",
    )
    op.create_table(
        "todo_changes",
        sa.Column("task_id", sa.UUID(), sa.ForeignKey("todo_tasks.id"), primary_key=True),
        sa.Column("revision", sa.Integer(), primary_key=True),
        sa.Column("actor_id", sa.UUID(), sa.ForeignKey("users.id")),
        sa.Column("action", sa.String(16), nullable=False),
        sa.Column("changes", JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "revision > 0 and action in ('baseline','created','updated')", name="ck_todo_change_values"
        ),
    )
    op.execute(
        "insert into todo_changes(task_id,revision,action,changes) select id,revision,'baseline','{}'::jsonb from todo_tasks"
    )


def downgrade():
    if op.get_bind().scalar(sa.text("select exists(select 1 from todo_changes)")):
        raise RuntimeError("Task history exists; downgrade would discard user evidence")
    op.drop_table("todo_changes")
    op.drop_constraint("ck_todo_task_status", "todo_tasks", type_="check")
    op.drop_column("todo_tasks", "status")
