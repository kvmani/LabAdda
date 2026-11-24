"""To-do lists, tasks, their change history, comments and sources."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, _created, _uuid_pk

if TYPE_CHECKING:  # resolved by the declarative registry at run time
    from .identity import User


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
