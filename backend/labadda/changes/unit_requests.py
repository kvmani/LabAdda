"""Bounded inputs for organisation-unit changes (PO-19); executable steps never come from clients."""

import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .text import single_line as _single_line

CODE_PATTERN = r"^[A-Z0-9][A-Z0-9-]{1,23}$"


class UnitChange(BaseModel):
    """A change to organisation units, never to a project or group."""

    model_config = ConfigDict(extra="forbid")


def _name(value: object) -> object:
    value = _single_line(value)
    if value is None:
        raise ValueError("A unit name cannot be blank.")
    return value


def _code(value: object) -> object:
    """Codes are typed in imports and on the chart, so case and spacing are normalised once."""
    return value.strip().upper() if isinstance(value, str) else value


class UnitCreate(UnitChange):
    kind: Literal["unit_create"]
    parent_id: uuid.UUID
    name: str = Field(min_length=1, max_length=120, strict=True)
    code: str = Field(pattern=CODE_PATTERN, strict=True)
    head_id: uuid.UUID | None = None
    level: Literal["group", "division", "section"] | None = None

    _name = field_validator("name", mode="before")(_name)
    _code = field_validator("code", mode="before")(_code)


class UnitRename(UnitChange):
    kind: Literal["unit_rename"]
    unit_id: uuid.UUID
    name: str | None = Field(default=None, min_length=1, max_length=120, strict=True)
    code: str | None = Field(default=None, pattern=CODE_PATTERN, strict=True)

    @field_validator("name", mode="before")
    @classmethod
    def clean_name(cls, value: object) -> object:
        return None if value is None else _name(value)

    @field_validator("code", mode="before")
    @classmethod
    def clean_code(cls, value: object) -> object:
        return _code(value)

    @model_validator(mode="after")
    def something_changes(self) -> "UnitRename":
        if self.name is None and self.code is None:
            raise ValueError("Choose a new name, a new code, or both.")
        return self


class UnitMove(UnitChange):
    kind: Literal["unit_move"]
    unit_id: uuid.UUID
    new_parent_id: uuid.UUID


class UnitMerge(UnitChange):
    kind: Literal["unit_merge"]
    unit_id: uuid.UUID
    into_unit_id: uuid.UUID


class UnitSplit(UnitChange):
    """Create a sibling of the source unit and move the chosen people into it."""

    kind: Literal["unit_split"]
    unit_id: uuid.UUID
    name: str = Field(min_length=1, max_length=120, strict=True)
    code: str = Field(pattern=CODE_PATTERN, strict=True)
    person_ids: list[uuid.UUID] = Field(min_length=1, max_length=200)
    acknowledge_no_steward: bool = Field(default=False, strict=True)

    _name = field_validator("name", mode="before")(_name)
    _code = field_validator("code", mode="before")(_code)

    @field_validator("person_ids")
    @classmethod
    def distinct_people(cls, value: list[uuid.UUID]) -> list[uuid.UUID]:
        """A stable order keeps equal selections on the same digest."""
        return sorted(set(value), key=str)


class UnitClose(UnitChange):
    kind: Literal["unit_close"]
    unit_id: uuid.UUID


class UnitReopen(UnitChange):
    kind: Literal["unit_reopen"]
    unit_id: uuid.UUID
