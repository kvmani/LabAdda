"""Immutable observation-only site policy proposals.

Revision ID: 0006
Revises: 0005
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = '0006'
down_revision = '0005'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('policy_drafts',
        sa.Column('id', sa.UUID(), primary_key=True),
        sa.Column('revision', sa.Integer(), nullable=False, unique=True),
        sa.Column('base_revision', sa.Integer(), nullable=False),
        sa.Column('schema_version', sa.Integer(), nullable=False),
        sa.Column('document', JSONB(), nullable=False),
        sa.Column('reason', sa.String(500), nullable=False),
        sa.Column('created_by', sa.UUID(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint('revision > 0 and base_revision >= 0 and schema_version = 1', name='ck_policy_draft_version'))


def downgrade():
    bind = op.get_bind()
    if bind.scalar(sa.text('select count(*) from policy_drafts')):
        raise RuntimeError('Policy drafts exist; downgrade would discard governance history')
    op.drop_table('policy_drafts')
