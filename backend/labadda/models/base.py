"""Declarative base, shared column helpers and the fixed vocabularies of the data model."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    DateTime,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


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
