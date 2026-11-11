"""Read-only referenced-file inspection receipts."""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "storage_inspections",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("summary", JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint(
            "status in ('running','completed','partial','failed')", name="ck_storage_inspection_status"
        ),
    )


def downgrade():
    if op.get_bind().scalar(sa.text("select count(*) from storage_inspections")):
        raise RuntimeError("Storage inspections exist; downgrade would discard reconciliation evidence")
    op.drop_table("storage_inspections")
