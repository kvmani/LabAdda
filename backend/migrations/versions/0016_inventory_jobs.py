"""Durable operator inventory attempts with fenced leases."""
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from alembic import op

revision = '0016'
down_revision = '0015'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('inventory_jobs',
        sa.Column('id', sa.UUID(), primary_key=True),
        sa.Column('request_key', sa.String(64), nullable=False, unique=True),
        sa.Column('plan_digest', sa.String(64), nullable=False),
        sa.Column('parameters', JSONB(), nullable=False),
        sa.Column('state', sa.String(16), nullable=False),
        sa.Column('attempt', sa.Integer(), nullable=False),
        sa.Column('lease_until', sa.DateTime(timezone=True)),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint("state in ('queued','running','completed','partial','failed','paused','cancelled')", name='ck_inventory_job_state'),
        sa.CheckConstraint('attempt >= 0 and attempt <= 100', name='ck_inventory_job_attempt'),
        sa.CheckConstraint("(state = 'running') = (lease_until is not null)", name='ck_inventory_job_lease'))
    op.create_table('inventory_attempts',
        sa.Column('job_id', sa.UUID(), sa.ForeignKey('inventory_jobs.id'), primary_key=True),
        sa.Column('number', sa.Integer(), primary_key=True),
        sa.Column('state', sa.String(16), nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('heartbeat_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('finished_at', sa.DateTime(timezone=True)),
        sa.Column('receipt_id', sa.UUID(), sa.ForeignKey('storage_inspections.id')),
        sa.CheckConstraint("state in ('running','completed','partial','failed','expired','paused','cancelled')", name='ck_inventory_attempt_state'),
        sa.CheckConstraint('number > 0 and number <= 100', name='ck_inventory_attempt_number'))


def downgrade():
    if op.get_bind().scalar(sa.text('select exists(select 1 from inventory_jobs)')):
        raise RuntimeError('Inventory jobs exist; downgrade would discard attempt evidence')
    op.drop_table('inventory_attempts')
    op.drop_table('inventory_jobs')
