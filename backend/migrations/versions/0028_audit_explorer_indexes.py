"""Index the audit trail for the explorer's newest-first, actor, person and unit filters."""

from alembic import op

revision = "0028"
down_revision = "0027"
branch_labels = None
depends_on = None

INDEXES = (
    ("ix_audit_events_created_id", ["created_at", "id"]),
    ("ix_audit_events_actor", ["actor_id", "created_at"]),
    ("ix_audit_events_target", ["target_id", "created_at"]),
    ("ix_audit_events_scope", ["scope_id", "created_at"]),
)


def upgrade():
    for name, columns in INDEXES:
        op.create_index(name, "audit_events", columns)


def downgrade():
    # Indexes hold no data of their own, so removing them can never lose audit rows.
    for name, _ in reversed(INDEXES):
        op.drop_index(name, table_name="audit_events")
