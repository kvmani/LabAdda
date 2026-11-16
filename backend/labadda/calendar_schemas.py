"""Bounded calendar request and response contracts."""

import uuid
from datetime import datetime
from typing import Literal, Self

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator, model_validator


class EventTitle(BaseModel):
    model_config = ConfigDict(extra="forbid")

    @field_validator("title", check_fields=False)
    @classmethod
    def nonempty_title(cls, value):
        if value is not None and not value.strip():
            raise ValueError("Write an event title")
        return value.strip() if value else value


class EventCreate(EventTitle):
    scope_kind: Literal["site", "workspace", "personal"]
    workspace_id: uuid.UUID | None = None
    title: str = Field(min_length=1, max_length=140)
    description: str | None = Field(default=None, max_length=10000)
    location: str | None = Field(default=None, max_length=140)
    starts_at: AwareDatetime
    ends_at: AwareDatetime
    all_day: bool = False
    color: str | None = Field(default=None, max_length=32)

    @model_validator(mode="after")
    def check_dates_and_scope(self) -> Self:
        if self.starts_at > self.ends_at:
            raise ValueError("starts_at must be before or equal to ends_at")
        if self.scope_kind == "personal" and self.workspace_id is not None:
            raise ValueError("personal events cannot have a workspace_id")
        if self.scope_kind == "workspace" and self.workspace_id is None:
            raise ValueError("workspace events must have a workspace_id")
        if self.scope_kind == "site" and self.workspace_id is not None:
            raise ValueError("site events cannot have a workspace_id")
        return self


class EventUpdate(EventTitle):
    revision: int = Field(ge=1, strict=True)
    title: str | None = Field(default=None, min_length=1, max_length=140)
    description: str | None = Field(default=None, max_length=10000)
    location: str | None = Field(default=None, max_length=140)
    starts_at: AwareDatetime | None = None
    ends_at: AwareDatetime | None = None
    all_day: bool | None = None
    color: str | None = Field(default=None, max_length=32)


class CalendarSourceOut(BaseModel):
    id: str
    title: str
    kind: str
    level: str | None = None
    color: str
    can_write: bool
    inherited: bool = False


class CalendarEventOut(BaseModel):
    revision: int
    id: uuid.UUID
    scope_kind: str
    workspace_id: uuid.UUID | None
    workspace_name: str | None
    owner_id: uuid.UUID | None
    created_by: uuid.UUID
    creator_name: str | None
    title: str
    description: str | None
    location: str | None
    starts_at: AwareDatetime
    ends_at: AwareDatetime
    all_day: bool
    color: str | None
    created_at: datetime
    updated_at: datetime
    can_edit: bool
    can_delete: bool
