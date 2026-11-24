"""Posts, files, notes, notifications, chat, calendar, broadcasts, feedback and site settings."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    false,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, _created, _uuid_pk


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
    source_request_digest: Mapped[str | None] = mapped_column(String(64))
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
    feedback_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("feedback.id", name="fk_assets_feedback")
    )
    has_preview: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    preview_size: Mapped[int | None] = mapped_column(BigInteger)
    preview_sha256: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = _created()

    __table_args__ = (
        CheckConstraint("status in ('provisional','committed')", name="ck_asset_status"),
        CheckConstraint(
            "status = 'provisional' or post_id is not null or board_workspace_id is not null or "
            "chat_message_id is not null or feedback_id is not null",
            name="ck_asset_committed_owner",
        ),
        CheckConstraint(
            "num_nonnulls(post_id, board_workspace_id, chat_message_id, feedback_id) <= 1",
            name="ck_asset_single_owner",
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
        Index("ix_assets_feedback", "feedback_id"),
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


class NotificationPreference(Base):
    """Owner alert choices; absence means the compatible all-enabled default."""

    __tablename__ = "notification_preferences"
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), primary_key=True)
    mentions: Mapped[bool] = mapped_column(Boolean, nullable=False)
    official_notices: Mapped[bool] = mapped_column(Boolean, nullable=False)
    reminders: Mapped[bool] = mapped_column(Boolean, nullable=False)
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    __table_args__ = (CheckConstraint("revision > 0", name="ck_notification_preference_revision"),)


class SiteBroadcast(Base):
    """A site-wide announcement shown to every signed-in user (AD-11).

    Site configuration written by administrators, not user content, so it may be deleted.
    """

    __tablename__ = "site_broadcasts"
    id: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    message: Mapped[str] = mapped_column(String(300), nullable=False)
    level: Mapped[str] = mapped_column(String(8), nullable=False)
    starts_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    active: Mapped[bool] = mapped_column(Boolean, nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    __table_args__ = (
        CheckConstraint("level in ('info','warning')", name="ck_site_broadcasts_level"),
        CheckConstraint(
            "starts_at is null or ends_at is null or ends_at > starts_at", name="ck_site_broadcasts_window"
        ),
        CheckConstraint("revision > 0", name="ck_site_broadcasts_revision"),
        Index("ix_site_broadcasts_position", "position"),
    )


class Feedback(Base):
    """A message a signed-in person chose to send to the administrators (who may read it)."""

    __tablename__ = "feedback"
    id: Mapped[uuid.UUID] = _uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    client_id: Mapped[str] = mapped_column(String(64), nullable=False)
    username: Mapped[str] = mapped_column(String(80), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    category: Mapped[str] = mapped_column(String(12), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    route: Mapped[str | None] = mapped_column(String(200))
    software_version: Mapped[str] = mapped_column(String(40), nullable=False)
    commit: Mapped[str] = mapped_column(String(64), nullable=False)
    user_agent: Mapped[str | None] = mapped_column(String(300))
    screen: Mapped[str | None] = mapped_column(String(12))
    status: Mapped[str] = mapped_column(String(10), nullable=False, default="new")
    admin_note: Mapped[str | None] = mapped_column(Text)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    handled_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    handled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        CheckConstraint("category in ('problem','suggestion','question')", name="ck_feedback_category"),
        CheckConstraint("status in ('new','seen','resolved')", name="ck_feedback_status"),
        UniqueConstraint("user_id", "client_id", name="uq_feedback_user_client"),
        Index("ix_feedback_created", "created_at", "id"),
        Index("ix_feedback_status", "status", "created_at"),
    )


class FeedbackMail(Base):
    """The e-mail copy of one feedback message: an outbox row retried until sent or given up."""

    __tablename__ = "feedback_mail"
    feedback_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("feedback.id"), primary_key=True
    )
    status: Mapped[str] = mapped_column(String(8), nullable=False, default="queued")
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    next_attempt_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_error: Mapped[str | None] = mapped_column(String(200))
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        CheckConstraint("status in ('queued','sent','failed')", name="ck_feedback_mail_status"),
        Index("ix_feedback_mail_due", "status", "next_attempt_at"),
    )


class SystemSetting(Base):
    """Global system configuration managed in-app by administrators."""

    __tablename__ = "system_settings"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(String(255))
    updated_at: Mapped[datetime] = _created()
    updated_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )


class CalendarEvent(Base):
    """Event scheduled at site, workspace, or personal scope."""

    __tablename__ = "calendar_events"

    id: Mapped[uuid.UUID] = _uuid_pk()
    scope_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    workspace_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=True
    )
    owner_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=True
    )
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    revision: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    title: Mapped[str] = mapped_column(String(140), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    location: Mapped[str | None] = mapped_column(String(140))
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    reminder_start_processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    all_day: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=false())
    color: Mapped[str | None] = mapped_column(String(32))
    created_at: Mapped[datetime] = _created()
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        CheckConstraint("scope_kind in ('site','workspace','personal')", name="ck_calendar_events_scope"),
        CheckConstraint("starts_at <= ends_at", name="ck_calendar_events_dates"),
        Index("ix_calendar_events_time", "starts_at", "ends_at"),
        Index("ix_calendar_events_workspace", "workspace_id", "starts_at"),
        Index("ix_calendar_events_owner", "owner_id", "starts_at"),
        Index("ix_calendar_events_scope", "scope_kind", "starts_at"),
    )
