"""Revision context for protected whiteboard task references."""
from alembic import op
import sqlalchemy as sa

revision = '0022'
down_revision = '0021'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('todo_sources', sa.Column('board_workspace_id', sa.UUID(), sa.ForeignKey('boards.workspace_id', ondelete='SET NULL')))
    op.add_column('todo_sources', sa.Column('board_epoch', sa.Integer()))
    op.add_column('todo_sources', sa.Column('board_revision', sa.BigInteger()))
    op.drop_constraint('ck_todo_source_kind', 'todo_sources', type_='check')
    op.create_check_constraint('ck_todo_source_kind', 'todo_sources', 'num_nonnulls(post_id, chat_message_id, board_workspace_id) <= 1')
    op.create_check_constraint('ck_todo_source_board', 'todo_sources', '(board_epoch is null) = (board_revision is null) and (board_epoch is null or (board_epoch > 0 and board_revision >= 0)) and (board_workspace_id is null or board_epoch is not null) and ((post_id is null and chat_message_id is null) or board_epoch is null)')


def downgrade():
    if op.get_bind().scalar(sa.text('select exists(select 1 from todo_sources where board_epoch is not null)')):
        raise RuntimeError('Task board references exist; downgrade would discard revision context')
    op.drop_constraint('ck_todo_source_board', 'todo_sources', type_='check')
    op.drop_constraint('ck_todo_source_kind', 'todo_sources', type_='check')
    op.drop_column('todo_sources', 'board_revision')
    op.drop_column('todo_sources', 'board_epoch')
    op.drop_column('todo_sources', 'board_workspace_id')
    op.create_check_constraint('ck_todo_source_kind', 'todo_sources', 'post_id is null or chat_message_id is null')
