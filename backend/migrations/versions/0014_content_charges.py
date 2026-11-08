"""Versioned canonical text/board logical charges (DL-07, T17).

Posts, replies, chat messages and personal notes are charged by database
triggers, so every writer (API, fixtures, recovery, direct SQL) keeps the
ledger in the same transaction as the content change. Board objects are
charged by the board writers because their state is a fold of operations;
``boards.charges_epoch`` records which epoch's charges are complete so an
unreconciled historical board is reported as unknown, never as zero.

The ledger is derived data: downgrading drops it without losing content.
"""

import sqlalchemy as sa
from alembic import op

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None

TEXT_METHOD = "utf8-text-v1"

FUNCTIONS = """
CREATE FUNCTION labadda_utf8_octets(value text) RETURNS bigint
LANGUAGE sql IMMUTABLE PARALLEL SAFE AS $$
  SELECT octet_length(convert_to(coalesce(value, ''), 'UTF8'))::bigint
$$;

CREATE FUNCTION labadda_charge_text() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
  kind text := TG_ARGV[0];
  row_user uuid;
  row_workspace uuid;
  row_state text := 'live';
  row_bytes bigint;
BEGIN
  IF TG_OP = 'DELETE' THEN
    DELETE FROM content_charges WHERE item_type = kind AND item_key = OLD.id::text;
    RETURN OLD;
  END IF;
  IF kind = 'post' THEN
    row_user := NEW.author_id; row_workspace := NEW.workspace_id;
    row_bytes := labadda_utf8_octets(NEW.body);
    IF NEW.deleted_at IS NOT NULL THEN row_state := 'removed'; END IF;
  ELSIF kind = 'chat' THEN
    row_user := NEW.author_id; row_workspace := NEW.workspace_id;
    row_bytes := labadda_utf8_octets(NEW.body);
  ELSE
    row_user := NEW.owner_id; row_workspace := NULL;
    row_bytes := labadda_utf8_octets(NEW.title) + labadda_utf8_octets(NEW.body);
  END IF;
  INSERT INTO content_charges (item_type, item_key, user_id, workspace_id, method, state, bytes, updated_at)
  VALUES (kind, NEW.id::text, row_user, row_workspace, 'utf8-text-v1', row_state, row_bytes, now())
  ON CONFLICT (item_type, item_key) DO UPDATE
    SET user_id = EXCLUDED.user_id, workspace_id = EXCLUDED.workspace_id, method = EXCLUDED.method,
        state = EXCLUDED.state, bytes = EXCLUDED.bytes, updated_at = EXCLUDED.updated_at;
  RETURN NEW;
END $$;
"""

TRIGGERS = {
    "posts": ("post", "body, deleted_at, author_id, workspace_id"),
    "chat_messages": ("chat", "body, author_id, workspace_id"),
    "notes": ("note", "title, body, owner_id"),
}

BACKFILL = """
INSERT INTO content_charges (item_type, item_key, user_id, workspace_id, method, state, bytes)
SELECT 'post', id::text, author_id, workspace_id, 'utf8-text-v1',
       CASE WHEN deleted_at IS NULL THEN 'live' ELSE 'removed' END, labadda_utf8_octets(body) FROM posts
UNION ALL
SELECT 'chat', id::text, author_id, workspace_id, 'utf8-text-v1', 'live', labadda_utf8_octets(body) FROM chat_messages
UNION ALL
SELECT 'note', id::text, owner_id, NULL, 'utf8-text-v1', 'live',
       labadda_utf8_octets(title) + labadda_utf8_octets(body) FROM notes;
"""


def upgrade():
    op.create_table(
        "content_charges",
        sa.Column("item_type", sa.String(16), nullable=False),
        sa.Column("item_key", sa.String(200), nullable=False),
        sa.Column("user_id", sa.UUID(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("workspace_id", sa.UUID(), sa.ForeignKey("workspaces.id"), nullable=True),
        sa.Column("method", sa.String(32), nullable=False),
        sa.Column("state", sa.String(16), nullable=False),
        sa.Column("bytes", sa.BigInteger(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("item_type", "item_key"),
        sa.CheckConstraint("item_type in ('post','chat','note','board_object')", name="ck_content_charge_type"),
        sa.CheckConstraint("state in ('live','removed')", name="ck_content_charge_state"),
        sa.CheckConstraint("bytes >= 0", name="ck_content_charge_bytes"),
        sa.CheckConstraint("(item_type = 'note') = (workspace_id is null)", name="ck_content_charge_scope"),
    )
    op.create_index("ix_content_charges_user", "content_charges", ["user_id", "item_type"])
    op.create_index("ix_content_charges_workspace", "content_charges", ["workspace_id", "item_type"])
    op.add_column("boards", sa.Column("charges_epoch", sa.Integer(), nullable=True))
    op.execute(FUNCTIONS)
    for table, (kind, columns) in TRIGGERS.items():
        op.execute(
            f"CREATE TRIGGER trg_{table}_charge AFTER INSERT OR DELETE OR UPDATE OF {columns} ON {table} "
            f"FOR EACH ROW EXECUTE FUNCTION labadda_charge_text('{kind}')"
        )
    op.execute(BACKFILL)
    # Empty boards are trivially complete; boards with history await reconciliation.
    op.execute("UPDATE boards SET charges_epoch = epoch WHERE revision = 0")


def downgrade():
    for table in TRIGGERS:
        op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_charge ON {table}")
    op.execute("DROP FUNCTION IF EXISTS labadda_charge_text()")
    op.execute("DROP FUNCTION IF EXISTS labadda_utf8_octets(text)")
    op.drop_column("boards", "charges_epoch")
    op.drop_index("ix_content_charges_workspace", table_name="content_charges")
    op.drop_index("ix_content_charges_user", table_name="content_charges")
    op.drop_table("content_charges")
