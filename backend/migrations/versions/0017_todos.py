"""Personal and workspace to-do lists with revisioned tasks."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "0017"
down_revision = "0016"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "todo_lists",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("owner_id", sa.UUID(), sa.ForeignKey("users.id")),
        sa.Column("workspace_id", sa.UUID(), sa.ForeignKey("workspaces.id")),
        sa.Column("created_by", sa.UUID(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("client_id", sa.UUID(), nullable=False),
        sa.Column("create_digest", sa.String(64), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("(owner_id is null) <> (workspace_id is null)", name="ck_todo_list_scope"),
        sa.CheckConstraint("revision > 0", name="ck_todo_list_revision"),
        sa.UniqueConstraint("created_by", "client_id", name="uq_todo_list_request"),
    )
    op.create_index("ix_todo_list_owner", "todo_lists", ["owner_id", "id"])
    op.create_index("ix_todo_list_workspace", "todo_lists", ["workspace_id", "id"])
    op.create_table(
        "todo_tasks",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("list_id", sa.UUID(), sa.ForeignKey("todo_lists.id"), nullable=False),
        sa.Column("created_by", sa.UUID(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("client_id", sa.UUID(), nullable=False),
        sa.Column("create_digest", sa.String(64), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("due_date", sa.Date()),
        sa.Column("priority", sa.String(8), nullable=False),
        sa.Column("checklist", JSONB(), nullable=False),
        sa.Column("done", sa.Boolean(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "priority in ('low','normal','high') and revision > 0", name="ck_todo_task_values"
        ),
        sa.UniqueConstraint("created_by", "client_id", name="uq_todo_task_request"),
    )
    op.create_index("ix_todo_task_list", "todo_tasks", ["list_id", "id"])


def downgrade():
    if op.get_bind().scalar(sa.text("select exists(select 1 from todo_lists)")):
        raise RuntimeError("To-do lists exist; downgrade would discard user content")
    op.drop_table("todo_tasks")
    op.drop_table("todo_lists")
