"""Index original-byte admission by stable contributor identity."""
from alembic import op
revision = '0011'
down_revision = '0010'
branch_labels = None
depends_on = None


def upgrade():
    op.create_index('ix_assets_owner','assets',['owner_id'])


def downgrade():
    op.drop_index('ix_assets_owner',table_name='assets')
