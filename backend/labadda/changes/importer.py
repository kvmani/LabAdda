"""Strict, in-memory parsing of a staff-list CSV; nothing here touches the database or disk."""

import csv
import io
import unicodedata
from dataclasses import dataclass, field
from datetime import date

from ..errors import ApiError, Invalid
from ..people import USERNAME_RE
from .text import single_line

MAX_BYTES = 1024 * 1024
MAX_ROWS = 2000
MAX_CELL = 200
COLUMNS = (
    "employee_no",
    "username",
    "display_name",
    "designation",
    "unit_code",
    "role",
    "status",
    "effective_on",
)
TEMPLATE = (
    "﻿" + ",".join(COLUMNS) + "\r\n"
    "NM-1001,rohan.mehta,Rohan Mehta,Research Officer,TFS,member,active,2026-12-01\r\n"
)
ROLES = ("member", "steward")
STATUSES = ("active", "invited", "suspended", "retired", "left", "on_leave")
FORMULA_START = ("=", "+", "-", "@")


class UploadTooLarge(ApiError):
    status = 413
    code = "import_too_large"
    message = "That file is too large. Staff lists can be up to 1 MiB and 2,000 rows."


@dataclass
class Row:
    """One data line, with plain-English problems; formula-like text is kept as literal text."""

    line: int
    username: str = ""
    employee_no: str | None = None
    display_name: str | None = None
    designation: str | None = None
    unit_code: str | None = None
    role: str | None = None
    status: str | None = None
    effective_on: date | None = None
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def _bad(code: str, message: str) -> Invalid:
    return Invalid(code, message)


def decode(data: bytes) -> str:
    """Accept UTF-8 with or without a byte-order mark; refuse anything else before parsing."""
    if len(data) > MAX_BYTES:
        raise UploadTooLarge()
    if not data.strip():
        raise _bad("import_empty", "The file is empty.")
    if b"\x00" in data:
        raise _bad("import_not_csv", "That does not look like a CSV text file.")
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise _bad(
            "import_encoding",
            "The file is not UTF-8 text. In your spreadsheet choose Save As, CSV UTF-8, and try again.",
        ) from None


def _header(first: list[str]) -> list[str]:
    names = [name.strip().lower() for name in first]
    unknown = [name for name in names if name not in COLUMNS]
    if unknown:
        shown = ", ".join(sorted({name[:40] or "(blank)" for name in unknown}))
        raise _bad("import_header", f"The first line has columns we do not use: {shown}. Use the template.")
    if len(set(names)) != len(names):
        raise _bad("import_header", "A column name appears twice in the first line. Use the template.")
    if "username" not in names:
        raise _bad("import_header", "The first line must include a username column. Use the template.")
    return names


def _cell(value: str, name: str, row: Row) -> str | None:
    value = value.strip()
    if len(value) > MAX_CELL:
        row.errors.append(f"The {name} cell is longer than {MAX_CELL} characters.")
        return None
    try:
        cleaned = single_line(value)
    except ValueError:
        row.errors.append(f"The {name} cell contains control characters. Use plain text.")
        return None
    if isinstance(cleaned, str) and unicodedata.normalize("NFKC", cleaned).startswith(FORMULA_START):
        row.warnings.append(f"The {name} cell starts with '{cleaned[0]}'. It is saved as plain text.")
    return cleaned if isinstance(cleaned, str) else None


def _fill(row: Row, values: dict[str, str]) -> None:
    for name in ("employee_no", "display_name", "designation", "unit_code"):
        if name in values:
            setattr(row, name, _cell(values[name], name, row))
    username = (_cell(values["username"], "username", row) or "").lower()
    if not username:
        row.errors.append("The username is blank.")
    elif not USERNAME_RE.match(username):
        row.errors.append("The username must be 2-63 lowercase letters, digits, dot, dash or underscore.")
    row.username = username
    if row.unit_code:
        row.unit_code = row.unit_code.upper()
    for name, allowed in (("role", ROLES), ("status", STATUSES)):
        raw = _cell(values.get(name, ""), name, row)
        if raw and raw.lower() not in allowed:
            row.errors.append(f"The {name} must be one of: {', '.join(allowed)}.")
        elif raw:
            setattr(row, name, raw.lower())
    raw = _cell(values.get("effective_on", ""), "effective_on", row)
    if raw:
        try:
            row.effective_on = date.fromisoformat(raw)
        except ValueError:
            row.errors.append("The effective_on date must look like 2026-12-01.")


def _repeats(rows: list[Row]) -> None:
    """A repeated username or employee number would make two rows claim one person."""
    for key, label in (("username", "username"), ("employee_no", "employee number")):
        seen: dict[str, int] = {}
        for row in rows:
            value = getattr(row, key)
            if not value:
                continue
            if value in seen:
                row.errors.append(f"This {label} already appears on line {seen[value]}.")
            else:
                seen[value] = row.line


def parse(data: bytes) -> list[Row]:
    """Validate shape and cell formats; per-row problems are recorded, file problems are raised."""
    reader = csv.reader(io.StringIO(decode(data), newline=""), strict=True)
    try:
        first = next(reader, None)
        if first is None:
            raise _bad("import_empty", "The file is empty.")
        names = _header(first)
        rows: list[Row] = []
        for cells in reader:
            if not any(cell.strip() for cell in cells):
                continue
            if len(rows) >= MAX_ROWS:
                raise UploadTooLarge()
            row = Row(reader.line_num)
            rows.append(row)
            if len(cells) != len(names):
                row.errors.append(f"This line has {len(cells)} cells but the first line has {len(names)}.")
                continue
            _fill(row, dict(zip(names, cells, strict=True)))
    except csv.Error:
        raise _bad("import_not_csv", "That file could not be read as CSV. Use the template.") from None
    if not rows:
        raise _bad("import_empty", "The file has a first line but no people. Add rows below it.")
    _repeats(rows)
    return rows
