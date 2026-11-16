"""Allow atomic note edits without erasing the original before validation."""

import sqlalchemy as sa
from alembic import op

revision = "0045"
down_revision = "0044"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_constraint("ck_board_op_type", "board_ops", type_="check")
    op.create_check_constraint(
        "ck_board_op_type", "board_ops", "op_type in ('add','erase','move','undo','update')"
    )


def downgrade():
    if (
        op.get_bind()
        .execute(
            sa.text(
                "select exists(select 1 from board_ops where op_type = 'update' "
                "or (op_type = 'undo' and payload->>'target_type' = 'update'))"
            )
        )
        .scalar()
    ):
        raise RuntimeError("Atomic board edits exist; downgrade would make retained history unreadable")
    op.drop_constraint("ck_board_op_type", "board_ops", type_="check")
    op.create_check_constraint("ck_board_op_type", "board_ops", "op_type in ('add','erase','move','undo')")
