"""Turn an Excel or CSV staff sheet into checked rows; nothing here touches the database or disk."""

import csv
import io
import re
from dataclasses import dataclass, field

from ..errors import Invalid
from ..people import USERNAME_RE
from . import importer, xlsx
from .text import single_line

COLUMNS = {
    "fullname": "full_name",
    "division": "division",
    "section": "section",
    "empno": "emp_no",
    "email": "email",
    "extension": "extension",
    "group": "group",
    "residencephone": "residence_phone",
    "username": "username",
    "password": "password",
    "isactive": "is_active",
    "role": "role",
}
REQUIRED = ("full_name", "group", "emp_no", "username")
HEADERS = (
    "full_name",
    "division",
    "section",
    "Emp No",
    "email",
    "Extension",
    "Group",
    "Residence Phone",
    "username",
    "Password",
    "is_active",
    "role",
)
ROLES = ("member", "admin")
TRUE = ("true", "yes", "y", "1")
FALSE = ("false", "no", "n", "0")


@dataclass
class StaffRow:
    """One person line. ``password`` is held only for the request that reads the file."""

    line: int
    full_name: str = ""
    group: str | None = None
    division: str | None = None
    section: str | None = None
    emp_no: str = ""
    email: str = ""
    extension: str | None = None
    residence_phone: str | None = None
    username: str = ""
    password: str | None = field(default=None, repr=False)
    active: bool = True
    role: str = "member"
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def _bad(code: str, message: str) -> Invalid:
    return Invalid(code, message)


def is_staff_header(first: list[str]) -> bool:
    keys = {_key(name) for name in first}
    return "fullname" in keys or "empno" in keys


def _key(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.lower())


def header_names(first: list[str]) -> list[str]:
    """Match headers ignoring case, spaces and underscores; unknown or repeated columns are refused."""
    names, unknown = [], []
    for raw in first:
        found = COLUMNS.get(_key(raw))
        if found is None:
            unknown.append((raw.strip() or "(blank)")[:40])
        names.append(found or "")
    if unknown:
        raise _bad(
            "import_header",
            f"The first row has columns we do not use: {', '.join(unknown)}. "
            "Use the template and keep its column names.",
        )
    if len(set(names)) != len(names):
        raise _bad("import_header", "A column name appears twice in the first row. Use the template.")
    missing = [name for name in REQUIRED if name not in names]
    if missing:
        raise _bad(
            "import_header",
            f"The first row is missing these columns: {', '.join(missing)}. Use the template.",
        )
    return names


def _text(value: str, label: str, row: StaffRow) -> str | None:
    value = value.strip()
    if len(value) > importer.MAX_CELL:
        row.errors.append(f"The {label} cell is longer than {importer.MAX_CELL} characters.")
        return None
    try:
        cleaned = single_line(value)
    except ValueError:
        row.errors.append(f"The {label} cell contains control characters. Use plain text.")
        return None
    return cleaned if isinstance(cleaned, str) else None


def _flag(raw: str | None, row: StaffRow) -> bool:
    if not raw:
        return True
    if raw.lower() in TRUE:
        return True
    if raw.lower() in FALSE:
        return False
    row.errors.append("The is_active cell must be TRUE or FALSE, or left blank for TRUE.")
    return True


def _fill(row: StaffRow, values: dict[str, str], domain: str) -> None:
    clean = {name: _text(values.get(name, ""), name, row) for name in COLUMNS.values() if name != "password"}
    row.full_name = clean["full_name"] or ""
    row.group, row.division, row.section = clean["group"], clean["division"], clean["section"]
    row.emp_no = clean["emp_no"] or ""
    row.extension, row.residence_phone = clean["extension"], clean["residence_phone"]
    row.username = (clean["username"] or "").lower()
    row.active = _flag(clean["is_active"], row)
    password = values.get("password", "").strip("\r\n")
    row.password = password if password.strip() else None
    raw_role = (clean["role"] or "member").lower()
    if raw_role not in ROLES:
        row.errors.append("The role must be member or admin, or left blank for member.")
    row.role = raw_role if raw_role in ROLES else "member"
    _mandatory(row)
    _address(row, (clean["email"] or "").lower(), domain)


def _mandatory(row: StaffRow) -> None:
    for label, value in (
        ("full_name", row.full_name),
        ("Emp No", row.emp_no),
        ("username", row.username),
        ("Group", row.group or ""),
    ):
        if not value:
            row.errors.append(f"{label} is required but this row leaves it blank.")
    if row.username and not USERNAME_RE.match(row.username):
        row.errors.append("The username must be 2-63 lowercase letters, digits, dot, dash or underscore.")


def _address(row: StaffRow, email: str, domain: str) -> None:
    expected = f"{row.username}@{domain}"
    if not email:
        row.email = expected if row.username else ""
    elif row.username and email != expected:
        row.errors.append(f"The email must be {expected} (the username at the site's e-mail domain).")
        row.email = email
    else:
        row.email = email


def _repeats(rows: list[StaffRow]) -> None:
    """A repeated username or employee number would make two rows claim one person."""
    for key, label in (("username", "username"), ("emp_no", "employee number")):
        seen: dict[str, int] = {}
        for row in rows:
            value = getattr(row, key)
            if not value:
                continue
            if value in seen:
                row.errors.append(f"This {label} already appears on line {seen[value]}.")
            else:
                seen[value] = row.line


def _table(data: bytes) -> list[list[str]]:
    if xlsx.looks_like_xlsx(data):
        if len(data) > importer.MAX_BYTES:
            raise importer.UploadTooLarge()
        return xlsx.read_rows(data)
    text = importer.decode(data)
    try:
        return list(csv.reader(io.StringIO(text, newline=""), strict=True))
    except csv.Error:
        raise _bad("import_not_csv", "That file could not be read as CSV. Use the template.") from None


def parse(data: bytes, domain: str) -> list[StaffRow]:
    """Check the sheet's shape and every cell; per-row problems are recorded, file problems raised."""
    if not domain:
        raise _bad(
            "email_domain_missing",
            "The site's e-mail domain is not set yet, so e-mail addresses cannot be checked. "
            "Ask whoever runs the server to set it.",
        )
    table = _table(data)
    if not table or not any(cell.strip() for cell in table[0]):
        raise _bad("import_empty", "The file is empty.")
    names = header_names(table[0])
    rows: list[StaffRow] = []
    for number, cells in enumerate(table[1:], start=2):
        if not any(cell.strip() for cell in cells):
            continue
        if len(rows) >= importer.MAX_ROWS:
            raise importer.UploadTooLarge()
        row = StaffRow(number)
        rows.append(row)
        if len(cells) > len(names):
            row.errors.append("This row has more cells than the first row has columns.")
            continue
        padded = [*cells, *[""] * (len(names) - len(cells))]
        _fill(row, dict(zip(names, padded, strict=True)), domain)
    if not rows:
        raise _bad("import_empty", "The file has a first row but no people. Add rows below it.")
    _repeats(rows)
    return rows
