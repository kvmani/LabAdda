"""Owner-scoped, bounded-lifetime upload request identities."""
import sqlalchemy as sa
from alembic import op
revision = '0012'
down_revision = '0011'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('upload_receipts',
        sa.Column('id',sa.UUID(),primary_key=True),
        sa.Column('user_id',sa.UUID(),sa.ForeignKey('users.id'),nullable=False),
        sa.Column('request_key',sa.String(64),nullable=False),
        sa.Column('fingerprint',sa.String(64),nullable=False),
        sa.Column('state',sa.String(16),nullable=False),
        sa.Column('reservation_id',sa.UUID(),sa.ForeignKey('upload_reservations.id',ondelete='SET NULL')),
        sa.Column('asset_id',sa.UUID(),sa.ForeignKey('assets.id',ondelete='SET NULL')),
        sa.Column('expires_at',sa.DateTime(timezone=True),nullable=False),
        sa.Column('created_at',sa.DateTime(timezone=True),server_default=sa.text('now()'),nullable=False),
        sa.UniqueConstraint('user_id','request_key',name='uq_upload_receipt_user_key'),
        sa.CheckConstraint("state in ('pending','complete','failed') and expires_at > created_at",name='ck_upload_receipt_state'))
    op.create_index('ix_upload_receipts_reservation_id', 'upload_receipts', ['reservation_id'])
    op.create_index('ix_upload_receipts_asset_id', 'upload_receipts', ['asset_id'])


def downgrade():
    if op.get_bind().scalar(sa.text('select count(*) from upload_receipts')):
        raise RuntimeError('Upload receipts exist; downgrade would discard request identity history')
    op.drop_table('upload_receipts')
