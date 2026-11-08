"""Expected derivative integrity, without guessing historical measurements."""
import sqlalchemy as sa
from alembic import op

revision = '0013'
down_revision = '0012'
branch_labels = None
depends_on = None

PREVIEW_CONSTRAINT = """
(preview_size is null and preview_sha256 is null) or
(preview_size is not null and
 ((has_preview and preview_size > 0 and preview_sha256 is not null and length(preview_sha256) = 64) or
  (not has_preview and preview_size = 0 and preview_sha256 is null)))
"""


def upgrade():
    op.add_column('assets', sa.Column('preview_size', sa.BigInteger(), nullable=True))
    op.add_column('assets', sa.Column('preview_sha256', sa.String(64), nullable=True))
    op.create_check_constraint('ck_asset_preview_integrity', 'assets', PREVIEW_CONSTRAINT)


def downgrade():
    if op.get_bind().scalar(sa.text('select count(*) from assets where preview_size is not null')):
        raise RuntimeError('Preview measurements exist; downgrade would discard integrity evidence')
    op.drop_constraint('ck_asset_preview_integrity', 'assets', type_='check')
    op.drop_column('assets', 'preview_sha256')
    op.drop_column('assets', 'preview_size')
