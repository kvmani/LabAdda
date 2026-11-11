"""The single site notice banner (AD-11)."""

import sqlalchemy as sa
from alembic import op

revision = "0029"
down_revision = "0028"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "site_banner",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("message", sa.String(280), nullable=False),
        sa.Column("level", sa.String(8), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("id = 1", name="ck_site_banner_single"),
        sa.CheckConstraint("level in ('info','warning')", name="ck_site_banner_level"),
        sa.CheckConstraint("ends_at > starts_at", name="ck_site_banner_window"),
        sa.CheckConstraint("revision > 0", name="ck_site_banner_revision"),
    )


def downgrade():
    if op.get_bind().scalar(sa.text("select exists(select 1 from site_banner)")):
        raise RuntimeError("A site notice exists; downgrade would discard it")
    op.drop_table("site_banner")
