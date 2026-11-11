"""Bounded, normalized staff-change inputs; executable steps never come from clients."""

import unicodedata
import uuid
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator, model_validator

type Revision = Annotated[int, Field(strict=True, ge=1, le=2_147_483_647)]
type Reason = Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=500)]


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
        """Keep staff fields single-line and valid for PostgreSQL/UTF-8 JSON."""
        if isinstance(value, str):
            if any(unicodedata.category(character) in {"Cc", "Cs"} for character in value):
                raise ValueError("Use ordinary single-line text without control characters.")
            return value.strip() or None
        return value

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


class PreviewRequest(BaseModel):
    """Ask for a server-computed plan without authorizing a mutation."""

    model_config = ConfigDict(extra="forbid")
    request: EditPerson


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
