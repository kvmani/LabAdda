"""Persistent data model.

Schema changes are applied only through Alembic migrations in
``backend/migrations``. Keep this module and the migrations in step.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Double,
    ForeignKey,
    Identity,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


def _uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)


def _created() -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


# Workspace kinds. ``org`` nodes form the single-root organization tree.
# ``project`` spaces are administrator-created and invite-only.
# ``group`` spaces are user-created collaborative groups (S2.1) with direct
# grants only and no hierarchy.
WORKSPACE_KINDS = ("org", "project", "group")
ROLES = ("member", "steward")
POSTING_POLICIES = ("open", "read_only")


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = _uuid_pk()
    username: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    display_name: Mapped[str] = mapped_column(String(120), nullable=False)
    password_hash: Mapped[str | None] = mapped_column(Text)
    is_admin: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    must_set_password: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    home_workspace_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = _created()
    deactivated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    employee_no: Mapped[str | None] = mapped_column(String(64))
    designation: Mapped[str | None] = mapped_column(String(120))
    contact_email: Mapped[str | None] = mapped_column(String(254))
    contact_phone: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active", server_default="active")
    status_effective_on: Mapped[date | None] = mapped_column(Date)
    expected_return_on: Mapped[date | None] = mapped_column(Date)
    joined_on: Mapped[date | None] = mapped_column(Date)
    last_seen_on: Mapped[date | None] = mapped_column(Date)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")

    __table_args__ = (
        CheckConstraint("username = lower(username)", name="ck_users_username_lower"),
        UniqueConstraint("employee_no", name="uq_users_employee_no"),
        CheckConstraint(
            "status IN ('invited','active','on_leave','suspended','retired','left')",
            name="ck_users_staff_status",
        ),
        CheckConstraint("revision > 0", name="ck_users_revision"),
    )


class CredentialToken(Base):
    __tablename__ = "credential_tokens"

    id: Mapped[uuid.UUID] = _uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    purpose: Mapped[str] = mapped_column(String(16), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    created_at: Mapped[datetime] = _created()

    __table_args__ = (CheckConstraint("purpose in ('activation','reset')", name="ck_token_purpose"),)


class AuthSession(Base):
    __tablename__ = "auth_sessions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)  # SHA-256 of the cookie token
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    csrf_token: Mapped[str] = mapped_column(String(64), nullable=False)
    kind: Mapped[str] = mapped_column(String(16), nullable=False, default="normal")
    created_at: Mapped[datetime] = _created()
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Board-only (touch panel) sessions are bound to one workspace board.
    workspace_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workspaces.id", name="fk_auth_sessions_workspace")
    )
    end_reason: Mapped[str | None] = mapped_column(String(32))

    __table_args__ = (
        Index("ix_auth_sessions_user", "user_id"),
        CheckConstraint(
            "(kind = 'normal' and workspace_id is null) or (kind = 'board' and workspace_id is not null)",
            name="ck_auth_session_kind",
        ),
    )


class PanelPairing(Base):
    """One-time code a signed-in user creates to open one board on a shared touch panel."""

    __tablename__ = "panel_pairings"

    id: Mapped[uuid.UUID] = _uuid_pk()
    code_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workspaces.id"), nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = _created()


class Workspace(Base):
    __tablename__ = "workspaces"

    id: Mapped[uuid.UUID] = _uuid_pk()
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    parent_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("workspaces.id"))
    archived: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    posting_policy: Mapped[str] = mapped_column(String(16), nullable=False, default="open")
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", use_alter=True, name="fk_workspaces_created_by")
    )
    created_at: Mapped[datetime] = _created()

    __table_args__ = (
        CheckConstraint("kind in ('org','project','group')", name="ck_workspace_kind"),
        CheckConstraint("posting_policy in ('open','read_only')", name="ck_workspace_policy"),
        CheckConstraint("kind = 'org' or parent_id is null", name="ck_workspace_flat_spaces"),
        CheckConstraint("parent_id is null or parent_id <> id", name="ck_workspace_not_own_parent"),
        Index(
            "uq_workspace_single_root",
            "kind",
            unique=True,
            postgresql_where=text("kind = 'org' and parent_id is null"),
        ),
        Index("ix_workspaces_parent", "parent_id"),
        Index("ix_workspaces_kind_created_by", "kind", "created_by"),
    )


class Membership(Base):
    __tablename__ = "memberships"

    id: Mapped[uuid.UUID] = _uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workspaces.id"), nullable=False
    )
    role: Mapped[str] = mapped_column(String(16), nullable=False, default="member")
    created_at: Mapped[datetime] = _created()

    __table_args__ = (
        UniqueConstraint("user_id", "workspace_id", name="uq_membership_user_workspace"),
        CheckConstraint("role in ('member','steward')", name="ck_membership_role"),
        Index("ix_memberships_workspace", "workspace_id"),
    )


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    scope_type: Mapped[str] = mapped_column(String(32), nullable=False)
    scope_id: Mapped[str | None] = mapped_column(String(64))
    target_id: Mapped[str | None] = mapped_column(String(64))
    outcome: Mapped[str] = mapped_column(String(16), nullable=False, default="success")
    reason: Mapped[str | None] = mapped_column(Text)
    detail: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = _created()

    __table_args__ = (
        Index("ix_audit_events_created_id", "created_at", "id"),
        Index("ix_audit_events_actor", "actor_id", "created_at"),
        Index("ix_audit_events_target", "target_id", "created_at"),
        Index("ix_audit_events_scope", "scope_id", "created_at"),
    )


class Post(Base):
    __tablename__ = "posts"

    id: Mapped[uuid.UUID] = _uuid_pk()
    seq: Mapped[int] = mapped_column(BigInteger, Identity(), nullable=False, unique=True)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workspaces.id"), nullable=False
    )
    author_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    parent_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("posts.id"))
    kind: Mapped[str] = mapped_column(String(16), nullable=False, default="discussion")
    body: Mapped[str] = mapped_column(Text, nullable=False)
    pinned: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    remind_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reminder_processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    client_id: Mapped[str | None] = mapped_column(String(64))
    # Set on a published board snapshot: where and at which revision it was captured.
    source_workspace_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workspaces.id", name="fk_posts_source_workspace")
    )
    source_revision: Mapped[int | None] = mapped_column(BigInteger)
    created_at: Mapped[datetime] = _created()
    edited_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    removed_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    removed_reason: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        CheckConstraint("kind in ('discussion','official')", name="ck_post_kind"),
        UniqueConstraint("author_id", "client_id", name="uq_post_client_id"),
        Index("ix_posts_workspace_seq", "workspace_id", "seq"),
        Index("ix_posts_parent", "parent_id"),
        Index(
            "ix_posts_pending_reminder", "remind_at", postgresql_where=text("reminder_processed_at is null")
        ),
    )


class Asset(Base):
    __tablename__ = "assets"

    id: Mapped[uuid.UUID] = _uuid_pk()
    owner_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    media_type: Mapped[str] = mapped_column(String(64), nullable=False)
    size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="provisional")
    post_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("posts.id"))
    chat_message_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("chat_messages.id")
    )
    board_workspace_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workspaces.id", name="fk_assets_board_workspace")
    )
    has_preview: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    preview_size: Mapped[int | None] = mapped_column(BigInteger)
    preview_sha256: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = _created()

    __table_args__ = (
        CheckConstraint("status in ('provisional','committed')", name="ck_asset_status"),
        CheckConstraint(
            "status = 'provisional' or post_id is not null or board_workspace_id is not null or "
            "chat_message_id is not null",
            name="ck_asset_committed_owner",
        ),
        CheckConstraint(
            "num_nonnulls(post_id, board_workspace_id, chat_message_id) <= 1", name="ck_asset_single_owner"
        ),
        CheckConstraint(
            "(preview_size is null and preview_sha256 is null) or "
            "(preview_size is not null and "
            "((has_preview and preview_size > 0 and preview_sha256 is not null and length(preview_sha256) "
            "= 64) or "
            "(not has_preview and preview_size = 0 and preview_sha256 is null)))",
            name="ck_asset_preview_integrity",
        ),
        Index("ix_assets_owner", "owner_id"),
        Index("ix_assets_post", "post_id"),
        Index("ix_assets_chat", "chat_message_id"),
        Index("ix_assets_board", "board_workspace_id"),
    )


class Note(Base):
    __tablename__ = "notes"

    id: Mapped[uuid.UUID] = _uuid_pk()
    owner_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    body: Mapped[str] = mapped_column(Text, nullable=False, default="")
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    remind_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reminder_processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = _created()
    updated_at: Mapped[datetime] = _created()

    __table_args__ = (Index("ix_notes_owner", "owner_id"),)


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[uuid.UUID] = _uuid_pk()
    recipient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    workspace_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("workspaces.id"))
    source_type: Mapped[str] = mapped_column(String(16), nullable=False)
    source_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    dedupe_key: Mapped[str] = mapped_column(String(200), nullable=False, unique=True)
    created_at: Mapped[datetime] = _created()
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (Index("ix_notifications_recipient", "recipient_id", "created_at"),)


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id: Mapped[uuid.UUID] = _uuid_pk()
    seq: Mapped[int] = mapped_column(BigInteger, Identity(), nullable=False, unique=True)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workspaces.id"), nullable=False
    )
    author_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    parent_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("chat_messages.id"))
    body: Mapped[str] = mapped_column(Text, nullable=False)
    client_id: Mapped[str] = mapped_column(String(64), nullable=False)
    attachments: Mapped[list[Asset]] = relationship(
        foreign_keys="Asset.chat_message_id", lazy="selectin", order_by="Asset.id"
    )
    created_at: Mapped[datetime] = _created()

    __table_args__ = (
        UniqueConstraint("author_id", "client_id", name="uq_chat_client_id"),
        CheckConstraint("parent_id is null or parent_id <> id", name="ck_chat_not_self"),
        Index("ix_chat_parent_seq", "parent_id", "seq"),
        Index("ix_chat_workspace_seq", "workspace_id", "seq"),
    )


class ChatRead(Base):
    __tablename__ = "chat_reads"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), primary_key=True)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workspaces.id"), primary_key=True
    )
    last_seq: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)


class Board(Base):
    __tablename__ = "boards"

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workspaces.id"), primary_key=True
    )
    epoch: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    revision: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    # Operations at or below this revision live only in board_snapshots.
    base_revision: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default="0", default=0)
    # Epoch whose board-object charges are complete; null or older means "unknown" (DL-07).
    charges_epoch: Mapped[int | None] = mapped_column(Integer)


class BoardSnapshot(Base):
    __tablename__ = "board_snapshots"

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workspaces.id"), primary_key=True
    )
    epoch: Mapped[int] = mapped_column(Integer, primary_key=True)
    revision: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    state: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = _created()


class BoardOp(Base):
    __tablename__ = "board_ops"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workspaces.id"), nullable=False
    )
    epoch: Mapped[int] = mapped_column(Integer, nullable=False)
    revision: Mapped[int] = mapped_column(BigInteger, nullable=False)
    op_id: Mapped[str] = mapped_column(String(64), nullable=False)
    actor_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    op_type: Mapped[str] = mapped_column(String(16), nullable=False)
    object_id: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = _created()

    __table_args__ = (
        UniqueConstraint("workspace_id", "epoch", "actor_id", "op_id", name="uq_board_op_identity"),
        UniqueConstraint("workspace_id", "revision", name="uq_board_op_revision"),
        CheckConstraint("op_type in ('add','erase','undo','move')", name="ck_board_op_type"),
    )


class PolicyDraft(Base):
    """Immutable, non-enforcing site policy proposals; activation is a later gate."""

    __tablename__ = "policy_drafts"
    id: Mapped[uuid.UUID] = _uuid_pk()
    revision: Mapped[int] = mapped_column(Integer, nullable=False, unique=True)
    base_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    schema_version: Mapped[int] = mapped_column(Integer, nullable=False)
    document: Mapped[dict] = mapped_column(JSONB, nullable=False)
    reason: Mapped[str] = mapped_column(String(500), nullable=False)
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = _created()
    __table_args__ = (
        CheckConstraint(
            "revision > 0 and base_revision >= 0 and schema_version in (1,2)", name="ck_policy_draft_version"
        ),
    )


class UsageObservation(Base):
    """Bounded retained site observations, never a complete quota ledger."""

    __tablename__ = "usage_observations"
    id: Mapped[uuid.UUID] = _uuid_pk()
    schema_version: Mapped[int] = mapped_column(Integer, nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = _created()
    __table_args__ = (CheckConstraint("schema_version = 1", name="ck_usage_observation_version"),)


class StorageInspection(Base):
    """Operator-triggered, read-only referenced-file reconciliation evidence."""

    __tablename__ = "storage_inspections"
    id: Mapped[uuid.UUID] = _uuid_pk()
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    summary: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = _created()
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        CheckConstraint(
            "status in ('running','completed','partial','failed')", name="ck_storage_inspection_status"
        ),
    )


class UsageReaderGrant(Base):
    """Time-limited site operational metadata access, not an administrator role."""

    __tablename__ = "usage_reader_grants"
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), primary_key=True)
    granted_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    reason: Mapped[str] = mapped_column(String(500), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = _created()


class UploadReservation(Base):
    """Pending original-byte admission. Durable assets replace these on commit."""

    __tablename__ = "upload_reservations"
    id: Mapped[uuid.UUID] = _uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = _created()
    __table_args__ = (
        CheckConstraint("bytes > 0 and expires_at > created_at", name="ck_upload_reservation_bounds"),
    )


class UploadReceipt(Base):
    """Owner-scoped 24-hour request identity; never an access grant."""

    __tablename__ = "upload_receipts"
    id: Mapped[uuid.UUID] = _uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    request_key: Mapped[str] = mapped_column(String(64), nullable=False)
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    state: Mapped[str] = mapped_column(String(16), nullable=False)
    reservation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("upload_reservations.id", ondelete="SET NULL"), index=True
    )
    asset_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("assets.id", ondelete="SET NULL"), index=True
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = _created()
    __table_args__ = (
        UniqueConstraint("user_id", "request_key", name="uq_upload_receipt_user_key"),
        CheckConstraint(
            "state in ('pending','complete','failed') and expires_at > created_at",
            name="ck_upload_receipt_state",
        ),
    )


class ContentCharge(Base):
    """Logical text/board charge per item under a versioned canonical rule (DL-07).

    Text rows are maintained by database triggers; board-object rows by the board writers.
    Derived data: reconcilable from source content, never an access grant.
    """

    __tablename__ = "content_charges"
    item_type: Mapped[str] = mapped_column(String(16), primary_key=True)
    item_key: Mapped[str] = mapped_column(String(200), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    workspace_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("workspaces.id"))
    method: Mapped[str] = mapped_column(String(32), nullable=False)
    state: Mapped[str] = mapped_column(String(16), nullable=False)
    bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    updated_at: Mapped[datetime] = _created()
    __table_args__ = (
        CheckConstraint("item_type in ('post','chat','note','board_object')", name="ck_content_charge_type"),
        CheckConstraint("state in ('live','removed')", name="ck_content_charge_state"),
        CheckConstraint("bytes >= 0", name="ck_content_charge_bytes"),
        CheckConstraint("(item_type = 'note') = (workspace_id is null)", name="ck_content_charge_scope"),
        Index("ix_content_charges_user", "user_id", "item_type"),
        Index("ix_content_charges_workspace", "workspace_id", "item_type"),
    )


class InventoryJob(Base):
    """Operator-only observation job. Leases fence accepted results, never delete files."""

    __tablename__ = "inventory_jobs"
    id: Mapped[uuid.UUID] = _uuid_pk()
    request_key: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    plan_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    parameters: Mapped[dict] = mapped_column(JSONB, nullable=False)
    state: Mapped[str] = mapped_column(String(16), nullable=False)
    attempt: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = _created()
    updated_at: Mapped[datetime] = _created()
    __table_args__ = (
        CheckConstraint(
            "state in ('queued','running','completed','partial','failed','paused','cancelled')",
            name="ck_inventory_job_state",
        ),
        CheckConstraint("attempt >= 0 and attempt <= 100", name="ck_inventory_job_attempt"),
        CheckConstraint("(state = 'running') = (lease_until is not null)", name="ck_inventory_job_lease"),
    )


class InventoryAttempt(Base):
    __tablename__ = "inventory_attempts"
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("inventory_jobs.id"), primary_key=True
    )
    number: Mapped[int] = mapped_column(Integer, primary_key=True)
    state: Mapped[str] = mapped_column(String(16), nullable=False)
    started_at: Mapped[datetime] = _created()
    heartbeat_at: Mapped[datetime] = _created()
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    receipt_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("storage_inspections.id")
    )
    __table_args__ = (
        CheckConstraint(
            "state in ('running','completed','partial','failed','expired','paused','cancelled')",
            name="ck_inventory_attempt_state",
        ),
        CheckConstraint("number > 0 and number <= 100", name="ck_inventory_attempt_number"),
    )


class TodoList(Base):
    __tablename__ = "todo_lists"
    id: Mapped[uuid.UUID] = _uuid_pk()
    owner_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    workspace_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("workspaces.id"))
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    client_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    create_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = _created()
    __table_args__ = (
        CheckConstraint("(owner_id is null) <> (workspace_id is null)", name="ck_todo_list_scope"),
        CheckConstraint("revision > 0", name="ck_todo_list_revision"),
        UniqueConstraint("created_by", "client_id", name="uq_todo_list_request"),
        Index("ix_todo_list_owner", "owner_id", "id"),
        Index("ix_todo_list_workspace", "workspace_id", "id"),
    )


class TodoTask(Base):
    __tablename__ = "todo_tasks"
    id: Mapped[uuid.UUID] = _uuid_pk()
    list_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("todo_lists.id"), nullable=False
    )
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    client_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    create_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    due_date: Mapped[date | None] = mapped_column(Date)
    priority: Mapped[str] = mapped_column(String(8), nullable=False)
    checklist: Mapped[list] = mapped_column(JSONB, nullable=False)
    done: Mapped[bool] = mapped_column(Boolean, nullable=False)
    assignee_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    assignee: Mapped[User | None] = relationship(foreign_keys=[assignee_id], lazy="selectin")
    source: Mapped[TodoSource | None] = relationship("TodoSource", uselist=False, lazy="selectin")
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default="todo")
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = _created()
    updated_at: Mapped[datetime] = _created()
    __table_args__ = (
        CheckConstraint(
            "status in ('todo','in_progress','blocked','done') and done = (status = 'done')",
            name="ck_todo_task_status",
        ),
        CheckConstraint("priority in ('low','normal','high') and revision > 0", name="ck_todo_task_values"),
        UniqueConstraint("created_by", "client_id", name="uq_todo_task_request"),
        Index("ix_todo_task_assignee", "assignee_id", "id"),
        Index("ix_todo_task_list", "list_id", "id"),
    )


class TodoChange(Base):
    """Content history, governed by the task's list access; never an admin log."""

    __tablename__ = "todo_changes"
    task_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("todo_tasks.id"), primary_key=True
    )
    revision: Mapped[int] = mapped_column(Integer, primary_key=True)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    action: Mapped[str] = mapped_column(String(16), nullable=False)
    changes: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = _created()
    __table_args__ = (
        CheckConstraint(
            "revision > 0 and action in ('baseline','created','updated')", name="ck_todo_change_values"
        ),
    )


class TodoComment(Base):
    """Immutable task discussion entry under the current list audience."""

    __tablename__ = "todo_comments"
    id: Mapped[uuid.UUID] = _uuid_pk()
    task_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("todo_tasks.id"), nullable=False
    )
    author_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    author: Mapped[User] = relationship(foreign_keys=[author_id], lazy="selectin")
    client_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    create_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = _created()
    __table_args__ = (
        UniqueConstraint("author_id", "client_id", name="uq_todo_comment_request"),
        UniqueConstraint("task_id", "sequence", name="uq_todo_comment_sequence"),
        CheckConstraint("sequence > 0", name="ck_todo_comment_sequence"),
    )


class TodoSource(Base):
    """Protected reference, never a copied conversation or an access grant."""

    __tablename__ = "todo_sources"
    task_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("todo_tasks.id"), primary_key=True
    )
    post_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("posts.id", ondelete="SET NULL")
    )
    chat_message_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("chat_messages.id", ondelete="SET NULL")
    )
    board_workspace_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("boards.workspace_id", ondelete="SET NULL")
    )
    board_epoch: Mapped[int | None] = mapped_column(Integer)
    board_revision: Mapped[int | None] = mapped_column(BigInteger)
    __table_args__ = (
        CheckConstraint(
            "num_nonnulls(post_id, chat_message_id, board_workspace_id) <= 1", name="ck_todo_source_kind"
        ),
        CheckConstraint(
            "(board_epoch is null) = (board_revision is null) and (board_epoch is null or (board_epoch > 0 "
            "and board_revision >= 0)) and (board_workspace_id is null or board_epoch is not null) and "
            "((post_id is null and chat_message_id is null) or board_epoch is null)",
            name="ck_todo_source_board",
        ),
    )


class NotificationPreference(Base):
    """Owner alert choices; absence means the compatible all-enabled default."""

    __tablename__ = "notification_preferences"
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), primary_key=True)
    mentions: Mapped[bool] = mapped_column(Boolean, nullable=False)
    official_notices: Mapped[bool] = mapped_column(Boolean, nullable=False)
    reminders: Mapped[bool] = mapped_column(Boolean, nullable=False)
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    __table_args__ = (CheckConstraint("revision > 0", name="ck_notification_preference_revision"),)


class MetricSample(Base):
    """One catalogued metric value per bucket (AD-08); dimensions never hold content or paths."""

    __tablename__ = "metric_samples"
    bucket_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    resolution: Mapped[str] = mapped_column(String(8), primary_key=True)
    metric: Mapped[str] = mapped_column(String(64), primary_key=True)
    dimension: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[float] = mapped_column(Double, nullable=False)
    samples: Mapped[int] = mapped_column(BigInteger, nullable=False)
    __table_args__ = (
        CheckConstraint("resolution in ('minute','hour','day')", name="ck_metric_sample_resolution"),
        CheckConstraint("samples >= 0", name="ck_metric_sample_samples"),
        Index("ix_metric_samples_series", "metric", "resolution", "dimension", "bucket_start"),
    )


class ActivityDay(Base):
    """A person made at least one signed-in request on this site-local day; nothing else."""

    __tablename__ = "activity_days"
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), primary_key=True)
    day: Mapped[date] = mapped_column(Date, primary_key=True)
    __table_args__ = (Index("ix_activity_days_day", "day"),)
