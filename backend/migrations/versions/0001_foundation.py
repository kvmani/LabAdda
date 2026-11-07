"""Foundation: identity, sessions, workspace tree, memberships, audit

Revision ID: 0001
Revises: None
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '0001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('workspaces',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('kind', sa.String(length=16), nullable=False),
    sa.Column('name', sa.String(length=120), nullable=False),
    sa.Column('description', sa.Text(), nullable=False),
    sa.Column('parent_id', sa.UUID(), nullable=True),
    sa.Column('archived', sa.Boolean(), nullable=False),
    sa.Column('posting_policy', sa.String(length=16), nullable=False),
    sa.Column('created_by', sa.UUID(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("kind = 'org' or parent_id is null", name='ck_workspace_flat_spaces'),
    sa.CheckConstraint("kind in ('org','project')", name='ck_workspace_kind'),
    sa.CheckConstraint("posting_policy in ('open','read_only')", name='ck_workspace_policy'),
    sa.CheckConstraint('parent_id is null or parent_id <> id', name='ck_workspace_not_own_parent'),
    sa.ForeignKeyConstraint(['parent_id'], ['workspaces.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_workspaces_parent', 'workspaces', ['parent_id'], unique=False)
    op.create_index('uq_workspace_single_root', 'workspaces', ['kind'], unique=True, postgresql_where=sa.text("kind = 'org' and parent_id is null"))
    op.create_table('users',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('username', sa.String(length=64), nullable=False),
    sa.Column('display_name', sa.String(length=120), nullable=False),
    sa.Column('password_hash', sa.Text(), nullable=True),
    sa.Column('is_admin', sa.Boolean(), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('must_set_password', sa.Boolean(), nullable=False),
    sa.Column('home_workspace_id', sa.UUID(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('deactivated_at', sa.DateTime(timezone=True), nullable=True),
    sa.CheckConstraint('username = lower(username)', name='ck_users_username_lower'),
    sa.ForeignKeyConstraint(['home_workspace_id'], ['workspaces.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('username')
    )
    op.create_table('auth_sessions',
    sa.Column('id', sa.String(length=64), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('csrf_token', sa.String(length=64), nullable=False),
    sa.Column('kind', sa.String(length=16), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('last_seen_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_auth_sessions_user', 'auth_sessions', ['user_id'], unique=False)
    op.create_table('credential_tokens',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('token_hash', sa.String(length=64), nullable=False),
    sa.Column('purpose', sa.String(length=16), nullable=False),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('used_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_by', sa.UUID(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("purpose in ('activation','reset')", name='ck_token_purpose'),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('token_hash')
    )
    op.create_table('memberships',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('workspace_id', sa.UUID(), nullable=False),
    sa.Column('role', sa.String(length=16), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("role in ('member','steward')", name='ck_membership_role'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('user_id', 'workspace_id', name='uq_membership_user_workspace')
    )
    op.create_index('ix_memberships_workspace', 'memberships', ['workspace_id'], unique=False)
    op.create_table('audit_events',
    sa.Column('id', sa.BigInteger(), sa.Identity(always=False), nullable=False),
    sa.Column('actor_id', sa.UUID(), nullable=True),
    sa.Column('action', sa.String(length=64), nullable=False),
    sa.Column('scope_type', sa.String(length=32), nullable=False),
    sa.Column('scope_id', sa.String(length=64), nullable=True),
    sa.Column('target_id', sa.String(length=64), nullable=True),
    sa.Column('outcome', sa.String(length=16), nullable=False),
    sa.Column('reason', sa.Text(), nullable=True),
    sa.Column('detail', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['actor_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_foreign_key('fk_workspaces_created_by', 'workspaces', 'users', ['created_by'], ['id'])
    # Defence in depth for S2: reject parent assignments that would form a cycle.
    op.execute("""
CREATE FUNCTION labadda_reject_workspace_cycle() RETURNS trigger AS $$
BEGIN
  IF NEW.parent_id IS NOT NULL AND EXISTS (
    WITH RECURSIVE up(id) AS (
      SELECT NEW.parent_id
      UNION ALL
      SELECT w.parent_id FROM workspaces w JOIN up ON w.id = up.id WHERE w.parent_id IS NOT NULL
    ) SELECT 1 FROM up WHERE id = NEW.id
  ) THEN
    RAISE EXCEPTION 'workspace hierarchy cycle' USING ERRCODE = 'check_violation';
  END IF;
  RETURN NEW;
END $$ LANGUAGE plpgsql;
""")
    op.execute("""
CREATE TRIGGER trg_workspace_cycle BEFORE INSERT OR UPDATE OF parent_id ON workspaces
FOR EACH ROW EXECUTE FUNCTION labadda_reject_workspace_cycle();
""")


def downgrade() -> None:
    op.execute('DROP TRIGGER IF EXISTS trg_workspace_cycle ON workspaces')
    op.execute('DROP FUNCTION IF EXISTS labadda_reject_workspace_cycle()')
    op.drop_constraint('fk_workspaces_created_by', 'workspaces', type_='foreignkey')
    op.drop_table('audit_events')
    op.drop_table('memberships')
    op.drop_table('credential_tokens')
    op.drop_table('auth_sessions')
    op.drop_table('users')
    op.drop_table('workspaces')
