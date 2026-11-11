"""Add staff records without inventing historical employment or sign-in dates."""

import sqlalchemy as sa
from alembic import op

revision = "0026"
down_revision = "0025"
branch_labels = None
depends_on = None

STAFF_FIELDS = (
    "employee_no",
    "designation",
    "contact_email",
    "contact_phone",
    "status_effective_on",
    "expected_return_on",
    "joined_on",
    "last_seen_on",
)


def upgrade():
    for name, length in (
        ("employee_no", 64),
        ("designation", 120),
        ("contact_email", 254),
        ("contact_phone", 64),
    ):
        op.add_column("users", sa.Column(name, sa.String(length), nullable=True))
    for name in STAFF_FIELDS[4:]:
        op.add_column("users", sa.Column(name, sa.Date(), nullable=True))
    op.add_column("users", sa.Column("status", sa.String(16), nullable=False, server_default="active"))
    op.add_column("users", sa.Column("revision", sa.Integer(), nullable=False, server_default="1"))
    op.execute(
        sa.text("""
        UPDATE users SET status = CASE
          WHEN NOT is_active THEN 'left'
          WHEN must_set_password THEN 'invited'
          ELSE 'active' END
    """)
    )
    op.create_unique_constraint("uq_users_employee_no", "users", ["employee_no"])
    op.create_check_constraint(
        "ck_users_staff_status",
        "users",
        "status IN ('invited','active','on_leave','suspended','retired','left')",
    )
    op.create_check_constraint("ck_users_revision", "users", "revision > 0")


def downgrade():
    # Default/backfilled states can be reconstructed from the old switches. New staff
    # fields, observed dates, revisions and distinct lifecycle states cannot be discarded.
    populated = op.get_bind().scalar(
        sa.text("""
        SELECT exists(SELECT 1 FROM users WHERE
          employee_no IS NOT NULL OR designation IS NOT NULL OR contact_email IS NOT NULL
          OR contact_phone IS NOT NULL OR status_effective_on IS NOT NULL
          OR expected_return_on IS NOT NULL OR joined_on IS NOT NULL OR last_seen_on IS NOT NULL
          OR revision <> 1 OR status <> CASE WHEN NOT is_active THEN 'left'
            WHEN must_set_password THEN 'invited' ELSE 'active' END)
    """)
    )
    if populated:
        raise RuntimeError("Staff records exist; downgrade would discard person data")
    op.drop_constraint("ck_users_revision", "users")
    op.drop_constraint("ck_users_staff_status", "users")
    op.drop_constraint("uq_users_employee_no", "users")
    for name in (*STAFF_FIELDS, "status", "revision"):
        op.drop_column("users", name)
