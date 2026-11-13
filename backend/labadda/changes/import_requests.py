"""Requests that only the Excel staff import builds; the passwords never travel in them."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, SecretStr

from .unit_requests import CODE_PATTERN

type UnitLevel = Literal["group", "division", "section"]


class PathNode(BaseModel):
    """One unit on the way down from the organisation: its name, level and the code a new one gets."""

    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=120, strict=True)
    level: UnitLevel
    code: str = Field(pattern=CODE_PATTERN, strict=True)


class ImportUnit(BaseModel):
    """Make sure the last unit of ``path`` exists under the ones before it, creating it if missing."""

    model_config = ConfigDict(extra="forbid")
    kind: Literal["import_unit"]
    path: list[PathNode] = Field(min_length=1, max_length=3)


class ImportPerson(BaseModel):
    """Create one account from a spreadsheet row, in the deepest unit named by ``path``."""

    model_config = ConfigDict(extra="forbid")
    kind: Literal["import_person"]
    username: str = Field(min_length=2, max_length=63, strict=True)
    display_name: str = Field(min_length=1, max_length=120, strict=True)
    employee_no: str = Field(min_length=1, max_length=64, strict=True)
    email: str = Field(min_length=3, max_length=254, strict=True)
    extension: str | None = Field(default=None, max_length=32, strict=True)
    residence_phone: str | None = Field(default=None, max_length=64, strict=True)
    path: list[PathNode] = Field(min_length=1, max_length=3)
    site_role: Literal["member", "admin"] = "member"
    active: bool = Field(default=True, strict=True)
    has_password: bool = Field(default=False, strict=True)
    # Excluded from every dump, so it can reach neither a plan, a digest, an audit row nor a response.
    password: SecretStr | None = Field(default=None, exclude=True, repr=False)
