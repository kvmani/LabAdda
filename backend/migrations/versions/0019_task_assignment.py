"""Nullable task assignment; no membership or create-request changes."""
from alembic import op
import sqlalchemy as sa

revision = '0019'
down_revision = '0018'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('todo_tasks',sa.Column('assignee_id',sa.UUID(),sa.ForeignKey('users.id')))
    op.create_index('ix_todo_task_assignee','todo_tasks',['assignee_id','id'])


def downgrade():
    if op.get_bind().scalar(sa.text("select exists(select 1 from todo_tasks where assignee_id is not null) or exists(select 1 from todo_changes where coalesce(changes->'assignee'->'before','null'::jsonb) <> 'null'::jsonb or coalesce(changes->'assignee'->'after','null'::jsonb) <> 'null'::jsonb)")):
        raise RuntimeError('Task assignments exist; downgrade would discard responsibility')
    op.drop_index('ix_todo_task_assignee',table_name='todo_tasks')
    op.drop_constraint('todo_tasks_assignee_id_fkey','todo_tasks',type_='foreignkey')
    op.drop_column('todo_tasks','assignee_id')
