"""Positions held in organisation units: Head, Deputy and additional charges (PO-13 to PO-18)."""

import sqlalchemy as sa
from alembic import op

revision = "0033"
down_revision = "0032"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "unit_positions",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("workspace_id", sa.UUID(), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("user_id", sa.UUID(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("position", sa.String(8), nullable=False),
        sa.Column("acting", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("starts_on", sa.Date(), nullable=False),
        sa.Column("ends_on", sa.Date()),
        sa.Column("revert_role", sa.String(8)),
        sa.Column("covers_id", sa.UUID(), sa.ForeignKey("unit_positions.id")),
        sa.Column("ended_at", sa.DateTime(timezone=True)),
        sa.Column("end_reason", sa.String(8)),
        sa.Column("created_by", sa.UUID(), sa.ForeignKey("users.id")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("position in ('head','deputy','charge')", name="ck_unit_position_kind"),
        sa.CheckConstraint("revert_role in ('member','steward','none')", name="ck_unit_position_revert"),
        sa.CheckConstraint("end_reason in ('expired','ended')", name="ck_unit_position_end_reason"),
        sa.CheckConstraint("ends_on is null or ends_on > starts_on", name="ck_unit_position_dates"),
        sa.CheckConstraint("not acting or ends_on is not null", name="ck_unit_position_acting_end"),
        sa.CheckConstraint("not acting or position <> 'charge'", name="ck_unit_position_acting_kind"),
        sa.CheckConstraint("(ended_at is null) = (end_reason is null)", name="ck_unit_position_ended"),
    )
    op.create_index(
        "uq_unit_positions_current_head",
        "unit_positions",
        ["workspace_id", "acting"],
        unique=True,
        postgresql_where=sa.text("position = 'head' AND ended_at IS NULL"),
    )
    op.create_index(
        "ix_unit_positions_due",
        "unit_positions",
        ["ends_on"],
        postgresql_where=sa.text("ended_at IS NULL AND ends_on IS NOT NULL"),
    )
    op.create_index(
        "ix_unit_positions_holder",
        "unit_positions",
        ["user_id"],
        postgresql_where=sa.text("ended_at IS NULL"),
    )
    op.create_index("ix_unit_positions_workspace", "unit_positions", ["workspace_id"])


def downgrade():
    if op.get_bind().scalar(sa.text("select exists(select 1 from unit_positions)")):
        raise RuntimeError("Unit positions exist; downgrade would discard the record of who held them")
    op.drop_index("ix_unit_positions_workspace", table_name="unit_positions")
    op.drop_index("ix_unit_positions_holder", table_name="unit_positions")
    op.drop_index("ix_unit_positions_due", table_name="unit_positions")
    op.drop_index("uq_unit_positions_current_head", table_name="unit_positions")
    op.drop_table("unit_positions")
