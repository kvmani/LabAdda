"""Accounts, credentials, sign-in sessions and touch-panel pairing."""

from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    false,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, _created, _uuid_pk


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
    extension: Mapped[str | None] = mapped_column(String(32))
    residence_phone: Mapped[str | None] = mapped_column(String(64))
    mobile: Mapped[str | None] = mapped_column(String(64))
    alternate_email: Mapped[str | None] = mapped_column(String(254))
    specialization: Mapped[str | None] = mapped_column(Text)
    avatar_data: Mapped[str | None] = mapped_column(Text)
    # Set when an administrator chose the first password: sign-in works, but only the change form does.
    must_change_password: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=false()
    )
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active", server_default="active")
    status_effective_on: Mapped[date | None] = mapped_column(Date)
    expected_return_on: Mapped[date | None] = mapped_column(Date)
    joined_on: Mapped[date | None] = mapped_column(Date)
    last_seen_on: Mapped[date | None] = mapped_column(Date)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    welcome_dismissed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    whats_new_seen_release: Mapped[str | None] = mapped_column(String(32))

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
    # Shown on the sessions list instead of the cookie-derived id, which is never published.
    public_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, default=uuid.uuid4, server_default=text("gen_random_uuid()")
    )
    agent_label: Mapped[str | None] = mapped_column(String(40))

    __table_args__ = (
        Index("ix_auth_sessions_user", "user_id"),
        Index("ux_auth_sessions_public_id", "public_id", unique=True),
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
