"""Site broadcasts replace the single site notice banner (AD-11)."""

import sqlalchemy as sa
from alembic import op

revision = "0039"
down_revision = "0038"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "site_broadcasts",
        sa.Column("id", sa.Integer(), sa.Identity(), primary_key=True),
        sa.Column("message", sa.String(300), nullable=False),
        sa.Column("level", sa.String(8), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True)),
        sa.Column("ends_at", sa.DateTime(timezone=True)),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("level in ('info','warning')", name="ck_site_broadcasts_level"),
        sa.CheckConstraint(
            "starts_at is null or ends_at is null or ends_at > starts_at", name="ck_site_broadcasts_window"
        ),
        sa.CheckConstraint("revision > 0", name="ck_site_broadcasts_revision"),
    )
    op.create_index("ix_site_broadcasts_position", "site_broadcasts", ["position"])
    # The existing single notice becomes the first broadcast.
    op.execute(
        """
        insert into site_broadcasts
            (message, level, starts_at, ends_at, active, position, revision, created_at, updated_at)
        select message, level, starts_at, ends_at, true, 1, 1, updated_at, updated_at from site_banner
        """
    )
    op.drop_table("site_banner")


def downgrade():
    bind = op.get_bind()
    rows = bind.execute(
        sa.text(
            "select message, level, starts_at, ends_at, updated_at from site_broadcasts order by position"
        )
    ).all()
    # One notice with both times fits the old table; anything else would be lost.
    if len(rows) > 1 or any(r.starts_at is None or r.ends_at is None or len(r.message) > 280 for r in rows):
        raise RuntimeError(
            "Broadcasts exist that the single site notice cannot hold; downgrade would discard them"
        )
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
    for row in rows:
        bind.execute(
            sa.text(
                "insert into site_banner (id, message, level, starts_at, ends_at, revision, updated_at) "
                "values (1, :message, :level, :starts_at, :ends_at, 1, :updated_at)"
            ),
            row._asdict(),
        )
    op.drop_table("site_broadcasts")
