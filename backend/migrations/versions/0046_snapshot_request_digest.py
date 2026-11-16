"""Bind snapshot retries to the complete source board, region and publication intent."""

import sqlalchemy as sa
from alembic import op

revision = "0046"
down_revision = "0045"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("posts", sa.Column("source_request_digest", sa.String(64), nullable=True))


def downgrade():
    if (
        op.get_bind()
        .execute(sa.text("select exists(select 1 from posts where source_request_digest is not null)"))
        .scalar()
    ):
        raise RuntimeError("Snapshot publication receipts exist; downgrade would discard retry integrity")
    op.drop_column("posts", "source_request_digest")
