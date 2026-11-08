"""Permit immutable version-two observation-only capacity proposals."""
import sqlalchemy as sa
from alembic import op

revision = '0015'
down_revision = '0014'
branch_labels = None
depends_on = None


def upgrade():
    op.drop_constraint('ck_policy_draft_version', 'policy_drafts', type_='check')
    op.create_check_constraint('ck_policy_draft_version', 'policy_drafts',
                               'revision > 0 and base_revision >= 0 and schema_version in (1,2)')


def downgrade():
    if op.get_bind().scalar(sa.text('select exists(select 1 from policy_drafts where schema_version = 2)')):
        raise RuntimeError('Capacity proposals exist; downgrade would discard governance compatibility')
    op.drop_constraint('ck_policy_draft_version', 'policy_drafts', type_='check')
    op.create_check_constraint('ck_policy_draft_version', 'policy_drafts',
                               'revision > 0 and base_revision >= 0 and schema_version = 1')
