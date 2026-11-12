"""Bounded, normalized staff-change inputs; executable steps never come from clients."""

import unicodedata
import uuid
from datetime import date
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator, model_validator

from ..people import USERNAME_RE
from .text import single_line as _single_line
from .unit_requests import (
    UnitClose,
    UnitCreate,
    UnitMerge,
    UnitMove,
    UnitRename,
    UnitReopen,
    UnitSplit,
)

type Revision = Annotated[int, Field(strict=True, ge=1, le=2_147_483_647)]
type Reason = Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=500)]
type Role = Literal["member", "steward"]
type Position = Literal["head", "deputy"]


def _ordinary_reason(value: str) -> str:
    if "\x00" in value or any(unicodedata.category(character) == "Cs" for character in value):
        raise ValueError("Use ordinary text for the reason.")
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


class PersonChange(BaseModel):
    """A change to one existing person."""

    model_config = ConfigDict(extra="forbid")
    person_id: uuid.UUID


def _distinct(value: list[uuid.UUID]) -> list[uuid.UUID]:
    """A stable order keeps equal selections on the same digest."""
    return sorted(set(value), key=str)


class Promote(PersonChange):
    """PO-13: a new designation and/or a role (optionally a vacant position) in one of their units."""

    kind: Literal["promote"]
    designation: str | None = Field(default=None, max_length=120, strict=True)
    workspace_id: uuid.UUID | None = None
    role: Role | None = None
    position: Position | None = None

    @field_validator("designation", mode="before")
    @classmethod
    def normalize_text(cls, value: object) -> object:
        return _single_line(value)

    @model_validator(mode="after")
    def coherent(self) -> "Promote":
        if "designation" not in self.model_fields_set and self.role is None:
            raise ValueError("Choose a new designation, a new role, or both.")
        if (self.workspace_id is None) != (self.role is None):
            raise ValueError("A role needs the unit or workspace it applies to.")
        if self.position is not None and self.role != "steward":
            raise ValueError("A Head or Deputy is always a steward.")
        return self


class ChangeAuthority(BaseModel):
    """PO-14: replace a unit's Head or a Deputy; an acting appointment has an end date."""

    model_config = ConfigDict(extra="forbid")
    kind: Literal["change_authority"]
    workspace_id: uuid.UUID
    position: Position
    successor_id: uuid.UUID
    acting: bool = Field(default=False, strict=True)
    ends_on: date | None = None
    replace_person_id: uuid.UUID | None = None
    outgoing_role: Role = "steward"

    @model_validator(mode="after")
    def dated(self) -> "ChangeAuthority":
        if self.acting and self.ends_on is None:
            raise ValueError("An acting appointment needs an end date.")
        if not self.acting and self.ends_on is not None:
            raise ValueError("Only acting appointments end on a date.")
        return self


class AdditionalCharge(PersonChange):
    """PO-15: access in a second unit, optionally with a position, optionally until a date."""

    kind: Literal["additional_charge"]
    workspace_id: uuid.UUID
    role: Role
    position: Position | None = None
    ends_on: date | None = None

    @model_validator(mode="after")
    def steward_for_position(self) -> "AdditionalCharge":
        if self.position is not None and self.role != "steward":
            raise ValueError("A Head or Deputy is always a steward.")
        return self


class ActingCover(BaseModel):
    """An acting replacement for one position the absent person holds."""

    model_config = ConfigDict(extra="forbid")
    position_id: uuid.UUID
    successor_id: uuid.UUID


class Leave(PersonChange):
    """PO-16: long leave with an expected return date; sign-in may be blocked."""

    kind: Literal["leave"]
    expected_return_on: date
    block_sign_in: bool = Field(default=False, strict=True)
    acting: list[ActingCover] = Field(default_factory=list, max_length=20)

    @field_validator("acting")
    @classmethod
    def one_cover_each(cls, value: list[ActingCover]) -> list[ActingCover]:
        if len({cover.position_id for cover in value}) != len(value):
            raise ValueError("Choose one acting replacement per position.")
        return sorted(value, key=lambda cover: str(cover.position_id))


class Return(PersonChange):
    """PO-16: back from leave; acting appointments made for the absence end."""

    kind: Literal["return"]


class Successor(BaseModel):
    """Who takes over a position or the last steward role in one workspace."""

    model_config = ConfigDict(extra="forbid")
    workspace_id: uuid.UUID
    successor_id: uuid.UUID
    acting: bool = Field(default=False, strict=True)
    ends_on: date | None = None

    @model_validator(mode="after")
    def dated(self) -> "Successor":
        if self.acting != (self.ends_on is not None):
            raise ValueError("An acting successor needs an end date; a permanent one has none.")
        return self


class Retire(PersonChange):
    """PO-17: retire or leave now; positions end and memberships are removed unless kept."""

    kind: Literal["retire"]
    status: Literal["retired", "left"]
    keep_workspace_ids: list[uuid.UUID] = Field(default_factory=list, max_length=100)
    successors: list[Successor] = Field(default_factory=list, max_length=50)
    acknowledge_no_steward: bool = Field(default=False, strict=True)

    @field_validator("keep_workspace_ids")
    @classmethod
    def distinct_workspaces(cls, value: list[uuid.UUID]) -> list[uuid.UUID]:
        return _distinct(value)

    @field_validator("successors")
    @classmethod
    def one_successor_each(cls, value: list[Successor]) -> list[Successor]:
        if len({item.workspace_id for item in value}) != len(value):
            raise ValueError("Choose one successor per workspace.")
        return sorted(value, key=lambda item: str(item.workspace_id))


class Suspend(PersonChange):
    """PO-18: stop access immediately."""

    kind: Literal["suspend"]


class Reinstate(PersonChange):
    """PO-18: back to invited with a new activation code and no access."""

    kind: Literal["reinstate"]


class GrantUnitAdmin(PersonChange):
    """PO-24: appoint a person to administer one unit's branch; site administrators only."""

    kind: Literal["unit_admin_grant"]
    unit_id: uuid.UUID


class RevokeUnitAdmin(PersonChange):
    """PO-24: withdraw an appointment; site administrators only."""

    kind: Literal["unit_admin_revoke"]
    unit_id: uuid.UUID


ChangeRequest = Annotated[
    EditPerson
    | AddPerson
    | Transfer
    | Promote
    | ChangeAuthority
    | AdditionalCharge
    | Leave
    | Return
    | Retire
    | Suspend
    | Reinstate
    | UnitCreate
    | UnitRename
    | UnitMove
    | UnitMerge
    | UnitSplit
    | UnitClose
    | UnitReopen
    | GrantUnitAdmin
    | RevokeUnitAdmin,
    Field(discriminator="kind"),
]


class PreviewRequest(BaseModel):
    """Ask for a server-computed plan without authorizing a mutation."""

    model_config = ConfigDict(extra="forbid")
    request: ChangeRequest
    effective_on: date | None = None


class ApplyRequest(PreviewRequest):
    """Confirm exactly the request, consequences and record revisions reviewed."""

    digest: str = Field(pattern="^[a-f0-9]{64}$", strict=True)
    revisions: dict[uuid.UUID, Revision] = Field(max_length=100)
    reason: Reason

    @field_validator("reason")
    @classmethod
    def valid_reason(cls, value: str) -> str:
        """Reject invalid Unicode and nulls without preventing ordinary multiline reasons."""
        return _ordinary_reason(value)


class ReissueRequest(BaseModel):
    """Ask for a fresh activation code for one invited person, with an audited reason."""

    model_config = ConfigDict(extra="forbid")
    person_id: uuid.UUID
    reason: Reason

    @field_validator("reason")
    @classmethod
    def valid_reason(cls, value: str) -> str:
        """Reasons are stored in the audit trail as ordinary text."""
        return _ordinary_reason(value)
