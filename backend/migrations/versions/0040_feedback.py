"""Feedback sent to the administrators, its attachments and its e-mail outbox (Pilot)."""

import sqlalchemy as sa
from alembic import op

revision = "0040"
down_revision = "0039"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "feedback",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("user_id", sa.UUID(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("client_id", sa.String(64), nullable=False),
        sa.Column("username", sa.String(80), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("category", sa.String(12), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("route", sa.String(200)),
        sa.Column("software_version", sa.String(40), nullable=False),
        sa.Column("commit", sa.String(64), nullable=False),
        sa.Column("user_agent", sa.String(300)),
        sa.Column("screen", sa.String(12)),
        sa.Column("status", sa.String(10), nullable=False),
        sa.Column("admin_note", sa.Text()),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("handled_by", sa.UUID(), sa.ForeignKey("users.id")),
        sa.Column("handled_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint("category in ('problem','suggestion','question')", name="ck_feedback_category"),
        sa.CheckConstraint("status in ('new','seen','resolved')", name="ck_feedback_status"),
        sa.UniqueConstraint("user_id", "client_id", name="uq_feedback_user_client"),
    )
    op.create_index("ix_feedback_created", "feedback", ["created_at", "id"])
    op.create_index("ix_feedback_status", "feedback", ["status", "created_at"])
    op.create_table(
        "feedback_mail",
        sa.Column("feedback_id", sa.UUID(), sa.ForeignKey("feedback.id"), primary_key=True),
        sa.Column("status", sa.String(8), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_error", sa.String(200)),
        sa.Column("sent_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint("status in ('queued','sent','failed')", name="ck_feedback_mail_status"),
    )
    op.create_index("ix_feedback_mail_due", "feedback_mail", ["status", "next_attempt_at"])
    op.add_column("assets", sa.Column("feedback_id", sa.UUID()))
    op.create_foreign_key("fk_assets_feedback", "assets", "feedback", ["feedback_id"], ["id"])
    op.create_index("ix_assets_feedback", "assets", ["feedback_id"])
    _owner_constraints("chat_message_id, feedback_id", " or feedback_id is not null")


def _owner_constraints(owners: str, committed_extra: str) -> None:
    op.drop_constraint("ck_asset_committed_owner", "assets")
    op.drop_constraint("ck_asset_single_owner", "assets")
    op.create_check_constraint(
        "ck_asset_committed_owner",
        "assets",
        "status = 'provisional' or post_id is not null or board_workspace_id is not null or "
        f"chat_message_id is not null{committed_extra}",
    )
    op.create_check_constraint(
        "ck_asset_single_owner",
        "assets",
        f"num_nonnulls(post_id, board_workspace_id, {owners}) <= 1",
    )


def downgrade():
    bind = op.get_bind()
    if bind.scalar(sa.text("select exists(select 1 from feedback)")):
        raise RuntimeError("Feedback exists; downgrade would discard what people sent to the administrators")
    op.drop_index("ix_assets_feedback", table_name="assets")
    _owner_constraints("chat_message_id", "")
    op.drop_constraint("fk_assets_feedback", "assets", type_="foreignkey")
    op.drop_column("assets", "feedback_id")
    op.drop_index("ix_feedback_mail_due", table_name="feedback_mail")
    op.drop_table("feedback_mail")
    op.drop_index("ix_feedback_status", table_name="feedback")
    op.drop_index("ix_feedback_created", table_name="feedback")
    op.drop_table("feedback")
