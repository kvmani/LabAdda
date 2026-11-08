"""Durable pending original-byte admission for the existing pilot quota."""
import sqlalchemy as sa
from alembic import op
revision = '0010'
down_revision = '0009'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('upload_reservations',
        sa.Column('id', sa.UUID(), primary_key=True),
        sa.Column('user_id', sa.UUID(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('bytes', sa.BigInteger(), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint('bytes > 0 and expires_at > created_at', name='ck_upload_reservation_bounds'))
    op.create_index('ix_upload_reservations_user_id','upload_reservations',['user_id'])


def downgrade():
    if op.get_bind().scalar(sa.text('select count(*) from upload_reservations')):
        raise RuntimeError('Upload reservations exist; stop upload workers and reconcile before downgrade')
    op.drop_table('upload_reservations')
