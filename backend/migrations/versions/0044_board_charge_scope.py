"""Partition derived board charges without changing any user content."""

import sqlalchemy as sa
from alembic import op

revision = "0044"
down_revision = "0043"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "content_charges", sa.Column("board_index", sa.Integer(), nullable=False, server_default="0")
    )
    # Old keys alone cannot disambiguate arbitrary object IDs containing colons.
    # Rebuild this derived ledger from retained board state, never from guessed keys.
    op.execute("delete from content_charges where item_type = 'board_object'")
    op.execute("update boards set charges_epoch = null where revision > 0")
    op.execute("update workspace_boards set charges_epoch = null where revision > 0")


def downgrade():
    op.execute("delete from content_charges where item_type = 'board_object'")
    op.execute("update boards set charges_epoch = null where revision > 0")
    op.execute("update workspace_boards set charges_epoch = null where revision > 0")
    op.drop_column("content_charges", "board_index")
