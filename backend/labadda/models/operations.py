"""Storage measurement, upload admission, metrics, activity days and operational events."""

from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
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
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, _created, _uuid_pk


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
    board_index: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
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


class OpsEvent(Base):
    """An operational event (AD-06): repeats of one code and component share a row while open."""

    __tablename__ = "ops_events"
    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    component: Mapped[str] = mapped_column(String(32), nullable=False)
    severity: Mapped[str] = mapped_column(String(8), nullable=False)
    summary: Mapped[str] = mapped_column(String(240), nullable=False)
    detail: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    first_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    state: Mapped[str] = mapped_column(String(12), nullable=False, default="open")
    acknowledged_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    note: Mapped[str | None] = mapped_column(Text)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        CheckConstraint("severity in ('info','warning','error','critical')", name="ck_ops_event_severity"),
        CheckConstraint("state in ('open','acknowledged','resolved')", name="ck_ops_event_state"),
        CheckConstraint("count >= 1", name="ck_ops_event_count"),
        Index("ix_ops_events_last", "last_at", "id"),
        Index("ix_ops_events_state", "state", "last_at"),
        # One live row per code and component: repeats raise the count instead (AD-06).
        Index(
            "uq_ops_events_live",
            "code",
            "component",
            unique=True,
            postgresql_where=text("state <> 'resolved'"),
        ),
    )
