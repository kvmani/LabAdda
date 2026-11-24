"""Workspaces, memberships, positions, authority grants, scheduled changes and the audit trail."""

from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
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
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, _created, _uuid_pk


class Workspace(Base):
    __tablename__ = "workspaces"

    id: Mapped[uuid.UUID] = _uuid_pk()
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    code: Mapped[str | None] = mapped_column(String(24))
    # Null means a plain "unit" made before levels existed.
    level: Mapped[str | None] = mapped_column(String(16))
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
        CheckConstraint(
            "level is null or (kind = 'org' and level in ('organisation','group','division','section'))",
            name="ck_workspace_level",
        ),
        CheckConstraint("posting_policy in ('open','read_only')", name="ck_workspace_policy"),
        CheckConstraint("kind = 'org' or parent_id is null", name="ck_workspace_flat_spaces"),
        CheckConstraint("parent_id is null or parent_id <> id", name="ck_workspace_not_own_parent"),
        CheckConstraint(
            "code is null or code ~ '^[A-Z0-9][A-Z0-9-]{1,23}$'", name="ck_workspace_code_format"
        ),
        Index(
            "uq_workspace_org_code",
            "code",
            unique=True,
            postgresql_where=text("kind = 'org' AND code IS NOT NULL"),
        ),
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


class UnitPosition(Base):
    """A Head, Deputy or additional charge in an organisation unit; ended rows are kept as history."""

    __tablename__ = "unit_positions"

    id: Mapped[uuid.UUID] = _uuid_pk()
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workspaces.id"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    position: Mapped[str] = mapped_column(String(8), nullable=False)
    acting: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=false())
    starts_on: Mapped[date] = mapped_column(Date, nullable=False)
    ends_on: Mapped[date | None] = mapped_column(Date)
    revert_role: Mapped[str | None] = mapped_column(String(8))
    covers_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("unit_positions.id"))
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    end_reason: Mapped[str | None] = mapped_column(String(8))
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    created_at: Mapped[datetime] = _created()

    __table_args__ = (
        CheckConstraint("position in ('head','deputy','charge')", name="ck_unit_position_kind"),
        CheckConstraint("revert_role in ('member','steward','none')", name="ck_unit_position_revert"),
        CheckConstraint("end_reason in ('expired','ended')", name="ck_unit_position_end_reason"),
        CheckConstraint("ends_on is null or ends_on > starts_on", name="ck_unit_position_dates"),
        CheckConstraint("not acting or ends_on is not null", name="ck_unit_position_acting_end"),
        CheckConstraint("not acting or position <> 'charge'", name="ck_unit_position_acting_kind"),
        CheckConstraint("(ended_at is null) = (end_reason is null)", name="ck_unit_position_ended"),
        # One current Head per unit, plus at most one acting Head while that Head is away.
        Index(
            "uq_unit_positions_current_head",
            "workspace_id",
            "acting",
            unique=True,
            postgresql_where=text("position = 'head' AND ended_at IS NULL"),
        ),
        Index(
            "ix_unit_positions_due",
            "ends_on",
            postgresql_where=text("ended_at IS NULL AND ends_on IS NOT NULL"),
        ),
        Index("ix_unit_positions_holder", "user_id", postgresql_where=text("ended_at IS NULL")),
        Index("ix_unit_positions_workspace", "workspace_id"),
    )


class ScheduledChange(Base):
    """A reviewed staff change that takes effect at the start of a future site day (PO-06)."""

    __tablename__ = "scheduled_changes"

    id: Mapped[uuid.UUID] = _uuid_pk()
    kind: Mapped[str] = mapped_column(String(24), nullable=False)
    request: Mapped[dict] = mapped_column(JSONB, nullable=False)
    plan_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    effective_on: Mapped[date] = mapped_column(Date, nullable=False)
    state: Mapped[str] = mapped_column(String(12), nullable=False, default="pending")
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    subject_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    steps: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    created_at: Mapped[datetime] = _created()
    applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    note: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        CheckConstraint(
            "state in ('pending','applied','cancelled','needs_review')", name="ck_scheduled_change_state"
        ),
        Index("ix_scheduled_changes_due", "effective_on", postgresql_where=text("state = 'pending'")),
        Index("ix_scheduled_changes_subject", "subject_id"),
        Index("ix_scheduled_changes_state", "state"),
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


class UsageReaderGrant(Base):
    """Time-limited site operational metadata access, not an administrator role."""

    __tablename__ = "usage_reader_grants"
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), primary_key=True)
    granted_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    reason: Mapped[str] = mapped_column(String(500), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = _created()


class UnitAdminGrant(Base):
    """Appoints a person to administer people and units of one branch; revoked rows stay as history."""

    __tablename__ = "unit_admin_grants"

    id: Mapped[uuid.UUID] = _uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workspaces.id"), nullable=False
    )
    granted_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    granted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        Index(
            "uq_unit_admin_grants_current",
            "user_id",
            "workspace_id",
            unique=True,
            postgresql_where=text("revoked_at IS NULL"),
        ),
        Index("ix_unit_admin_grants_workspace", "workspace_id"),
    )


class ContributionDelegation(Base):
    """A child unit's revocable representation at its immediate parent."""

    __tablename__ = "contribution_delegations"
    id: Mapped[uuid.UUID] = _uuid_pk()
    source_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    destination_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    granted_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = _created()
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")


class JoinRequest(Base):
    """A staff member's voluntary application to join the platform."""

    __tablename__ = "join_requests"
    __table_args__ = (Index("ix_join_requests_created_at", "created_at"),)
    id: Mapped[uuid.UUID] = _uuid_pk()
    created_at: Mapped[datetime] = _created()
    full_name: Mapped[str] = mapped_column(String(120), nullable=False)
    username: Mapped[str] = mapped_column(String(63), nullable=False, index=True)
    employee_no: Mapped[str | None] = mapped_column(String(64), index=True)
    contact_email: Mapped[str | None] = mapped_column(String(254))
    contact_phone: Mapped[str | None] = mapped_column(String(64))
    designation: Mapped[str | None] = mapped_column(String(120))
    unit_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("workspaces.id"))
    unit_name: Mapped[str | None] = mapped_column(String(120))
    statement_of_interest: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending", server_default="pending", index=True
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    review_note: Mapped[str | None] = mapped_column(String(500))
    created_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
