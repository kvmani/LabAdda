"""Shared and personal whiteboards: boards, operations, snapshots and revisions."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    ForeignKey,
    Identity,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, _created, _uuid_pk


class Board(Base):
    __tablename__ = "boards"

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workspaces.id"), primary_key=True
    )
    title: Mapped[str] = mapped_column(
        String(64), nullable=False, default="Board 1", server_default="Board 1"
    )
    epoch: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    revision: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    # Operations at or below this revision live only in board_snapshots.
    base_revision: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default="0", default=0)
    # Epoch whose board-object charges are complete; null or older means "unknown" (DL-07).
    charges_epoch: Mapped[int | None] = mapped_column(Integer)

    @property
    def board_index(self) -> int:
        return 0


class WorkspaceBoard(Base):
    """Secondary whiteboards (board_index >= 1) for a workspace."""

    __tablename__ = "workspace_boards"

    id: Mapped[uuid.UUID] = _uuid_pk()
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )
    board_index: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(
        String(64), nullable=False, default="Board 2", server_default="Board 2"
    )
    epoch: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    revision: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    base_revision: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default="0", default=0)
    charges_epoch: Mapped[int | None] = mapped_column(Integer)

    __table_args__ = (UniqueConstraint("workspace_id", "board_index", name="uq_workspace_boards_index"),)


class BoardSnapshot(Base):
    __tablename__ = "board_snapshots"

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workspaces.id"), primary_key=True
    )
    board_index: Mapped[int] = mapped_column(Integer, primary_key=True, default=0, server_default="0")
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
    board_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
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
        UniqueConstraint(
            "workspace_id", "board_index", "epoch", "actor_id", "op_id", name="uq_board_op_identity"
        ),
        UniqueConstraint("workspace_id", "board_index", "revision", name="uq_board_op_revision"),
        CheckConstraint("op_type in ('add','erase','undo','move','update')", name="ck_board_op_type"),
    )


class PersonalBoardRevision(Base):
    """Append-only owner-private board documents; older work survives later revisions."""

    __tablename__ = "personal_board_revisions"
    owner_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), primary_key=True)
    board_index: Mapped[int] = mapped_column(Integer, primary_key=True, default=0, server_default="0")
    revision: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(
        String(64), nullable=False, default="Board 1", server_default="Board 1"
    )
    objects: Mapped[list] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = _created()
