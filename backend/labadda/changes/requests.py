"""Bounded, normalized staff-change inputs; executable steps never come from clients."""

import unicodedata
import uuid
from datetime import date
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator, model_validator

from ..people import USERNAME_RE

type Revision = Annotated[int, Field(strict=True, ge=1, le=2_147_483_647)]
type Reason = Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=500)]
type Role = Literal["member", "steward"]


def _single_line(value: object) -> object:
    """Keep staff text single-line and valid for PostgreSQL/UTF-8 JSON."""
    if isinstance(value, str):
        if any(unicodedata.category(character) in {"Cc", "Cs"} for character in value):
            raise ValueError("Use ordinary single-line text without control characters.")
        return value.strip() or None
    return value


class StaffFields(BaseModel):
    """Permit only editable staff metadata, preserving omitted fields."""

    model_config = ConfigDict(extra="forbid")
    display_name: str | None = Field(default=None, min_length=1, max_length=120, strict=True)
    designation: str | None = Field(default=None, max_length=120, strict=True)
    employee_no: str | None = Field(default=None, max_length=64, strict=True)
    contact_email: str | None = Field(default=None, max_length=254, strict=True)
    contact_phone: str | None = Field(default=None, max_length=64, strict=True)

    @field_validator(
        "display_name", "designation", "employee_no", "contact_email", "contact_phone", mode="before"
    )
    @classmethod
    def normalize_text(cls, value: object) -> object:
        """Trim staff text; blank optional values become null."""
        return _single_line(value)

    @model_validator(mode="after")
    def validate_edit(self) -> "StaffFields":
        """Require a real selection of fields and a nonblank display name when selected."""
        if not self.model_fields_set:
            raise ValueError("Choose at least one staff field to change.")
        if "display_name" in self.model_fields_set and self.display_name is None:
            raise ValueError("A display name cannot be blank.")
        return self


class EditPerson(BaseModel):
    """Edit a staff record without changing username, access or employment status."""

    model_config = ConfigDict(extra="forbid")
    kind: Literal["edit_person"]
    person_id: uuid.UUID
    fields: StaffFields


class NewStaffFields(BaseModel):
    """Optional staff metadata recorded when an account is first created."""

    model_config = ConfigDict(extra="forbid")
    designation: str | None = Field(default=None, max_length=120, strict=True)
    employee_no: str | None = Field(default=None, max_length=64, strict=True)
    contact_email: str | None = Field(default=None, max_length=254, strict=True)
    contact_phone: str | None = Field(default=None, max_length=64, strict=True)

    @field_validator("designation", "employee_no", "contact_email", "contact_phone", mode="before")
    @classmethod
    def normalize_text(cls, value: object) -> object:
        """Trim staff text; blank optional values become null."""
        return _single_line(value)


class AddPerson(BaseModel):
    """Create an invited account with one home-unit membership; never an administrator."""

    model_config = ConfigDict(extra="forbid")
    kind: Literal["add_person"]
    username: str = Field(min_length=2, max_length=63, strict=True)
    display_name: str = Field(min_length=1, max_length=120, strict=True)
    fields: NewStaffFields = Field(default_factory=NewStaffFields)
    home_unit_id: uuid.UUID
    role: Role
    joined_on: date | None = None

    @field_validator("username", mode="before")
    @classmethod
    def normalize_username(cls, value: object) -> object:
        """Usernames are immutable, so the shared spelling rule is enforced before review."""
        if isinstance(value, str):
            value = value.strip().lower()
            if not USERNAME_RE.match(value):
                raise ValueError("Use 2-63 lowercase letters, digits, dot, dash or underscore.")
        return value

    @field_validator("display_name", mode="before")
    @classmethod
    def normalize_name(cls, value: object) -> object:
        """A display name is required and single-line."""
        value = _single_line(value)
        if value is None:
            raise ValueError("A display name cannot be blank.")
        return value


class Transfer(BaseModel):
    """Move a person's home unit; previous access is removed unless kept as additional access."""

    model_config = ConfigDict(extra="forbid")
    kind: Literal["transfer"]
    person_id: uuid.UUID
    to_unit_id: uuid.UUID
    role: Role
    keep_previous: bool = Field(default=False, strict=True)
    leave_workspace_ids: list[uuid.UUID] = Field(default_factory=list, max_length=100)
    acknowledge_no_steward: bool = Field(default=False, strict=True)

    @field_validator("leave_workspace_ids")
    @classmethod
    def distinct_workspaces(cls, value: list[uuid.UUID]) -> list[uuid.UUID]:
        """A stable order keeps equal selections on the same digest."""
        return sorted(set(value), key=str)


ChangeRequest = Annotated[EditPerson | AddPerson | Transfer, Field(discriminator="kind")]


class PreviewRequest(BaseModel):
    """Ask for a server-computed plan without authorizing a mutation."""

    model_config = ConfigDict(extra="forbid")
    request: ChangeRequest


class ApplyRequest(PreviewRequest):
    """Confirm exactly the request, consequences and record revisions reviewed."""

    digest: str = Field(pattern="^[a-f0-9]{64}$", strict=True)
    revisions: dict[uuid.UUID, Revision] = Field(max_length=100)
    reason: Reason

    @field_validator("reason")
    @classmethod
    def valid_reason(cls, value: str) -> str:
        """Reject invalid Unicode and nulls without preventing ordinary multiline reasons."""
        if "\x00" in value or any(unicodedata.category(character) == "Cs" for character in value):
            raise ValueError("Use ordinary text for the reason.")
        return value
