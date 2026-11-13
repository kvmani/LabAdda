"""Review and apply an Excel staff sheet through the ordinary bulk change protocol.

The sheet is read in memory twice, once to review and once to apply, because the first passwords
must never be kept between the two requests. The reviewed plan digest ties the two reads together.
"""

import re
import unicodedata

from pydantic import SecretStr, ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import Settings
from ..deps import Actor
from ..errors import Invalid
from ..models import User, Workspace
from ..realtime import Hub
from ..security import MIN_PASSWORD_LENGTH
from . import bulk, import_tree, service, staff_sheet
from .import_requests import ImportPerson, ImportUnit, PathNode
from .staff_sheet import StaffRow

LEVELS = ("group", "division", "section")
CODE_MAX = 12


def _code_stem(name: str) -> str:
    ascii_name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    words = re.findall(r"[A-Za-z0-9]+", ascii_name)
    stem = "".join(word[0] for word in words).upper()
    if len(stem) < 2 and words:
        stem = (words[0] + "XX")[:2].upper()
    return (stem or "UN")[:CODE_MAX]


class _Tree:
    """Names along every row's path, with a stable code for each unit that will be created."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.taken = set(db.scalars(select(Workspace.code).where(Workspace.kind == "org")))
        self.codes: dict[tuple[str, ...], str] = {}
        self.levels: dict[tuple[str, ...], str] = {}
        self.missing: dict[tuple[str, ...], list[PathNode]] = {}
        self.problems: dict[tuple[str, ...], list[str]] = {}

    def _code(self, name: str) -> str:
        stem = _code_stem(name)
        code, number = stem, 1
        while code in self.taken:
            number += 1
            code = f"{stem}-{number}"
        self.taken.add(code)
        return code

    def nodes(self, row: StaffRow) -> list[tuple[str, str]]:
        names = [(row.group, "group"), (row.division, "division"), (row.section, "section")]
        return [(name, level) for name, level in names if name]

    def add(self, row: StaffRow) -> list[PathNode] | None:
        """The row's path, or ``None`` after recording why it cannot be used."""
        path: list[PathNode] = []
        key: tuple[str, ...] = ()
        for name, level in self.nodes(row):
            key = (*key, import_tree.fold(name))
            if self.levels.setdefault(key, level) != level:
                row.errors.append(f"{name} is used as both a {self.levels[key]} and a {level} here.")
                return None
            if key not in self.codes:
                self.codes[key] = self._code(name)
            path.append(PathNode(name=name, level=level, code=self.codes[key]))
        return path

    def check(self, row: StaffRow, path: list[PathNode]) -> None:
        found = import_tree.find(self.db, path)
        row.errors += [blocker.message for blocker in found.blockers]
        key: tuple[str, ...] = ()
        for index, node in enumerate(path):
            key = (*key, import_tree.fold(node.name))
            if found.units[index] is None and key not in self.missing:
                self.missing[key] = path[: index + 1]


def _person(row: StaffRow, path: list[PathNode], with_passwords: bool) -> ImportPerson:
    return ImportPerson(
        kind="import_person",
        username=row.username,
        display_name=row.full_name,
        employee_no=row.emp_no,
        email=row.email,
        extension=row.extension,
        residence_phone=row.residence_phone,
        path=path,
        site_role=row.role,
        active=row.active,
        has_password=row.password is not None,
        password=SecretStr(row.password) if with_passwords and row.password else None,
    )


def _existing_checks(db: Session, rows: list[StaffRow]) -> None:
    names = set(db.scalars(select(User.username)))
    numbers = set(db.scalars(select(User.employee_no).where(User.employee_no.is_not(None))))
    for row in rows:
        if row.username in names:
            row.errors.append("That username already has an account. Remove this row.")
        if row.emp_no in numbers:
            row.errors.append("That employee number already belongs to someone.")
        if row.password is not None and len(row.password) < MIN_PASSWORD_LENGTH:
            row.errors.append(f"The password is too short. Use at least {MIN_PASSWORD_LENGTH} characters.")


def _entry(row: StaffRow, path: list[PathNode] | None) -> dict:
    place = " > ".join(node.name for node in path) if path else ""
    warnings = list(row.warnings)
    if row.role == "admin":
        warnings.append("Will become an administrator.")
    if not row.active:
        warnings.append("Sign-in will be switched off for this person.")
    return {
        "line": row.line,
        "display_name": row.full_name,
        "username": row.username,
        "place": place,
        "role": row.role,
        "access": "off" if not row.active else "password" if row.password else "code",
        "errors": row.errors,
        "warnings": warnings,
    }


def review(
    db: Session, data: bytes, settings: Settings, deadline: service.Deadline, *, with_passwords: bool = False
) -> tuple[dict, list]:
    """Rows, the units to create and the bulk requests; nothing is written."""
    rows = staff_sheet.parse(data, settings.email_domain)
    _existing_checks(db, rows)
    tree = _Tree(db)
    paths: dict[int, list[PathNode]] = {}
    for row in rows:
        deadline.check()
        if row.errors:
            continue
        path = tree.add(row)
        if path is not None:
            tree.check(row, path)
            paths[row.line] = path
    entries = [_entry(row, paths.get(row.line)) for row in rows]
    failed = sum(1 for row in rows if row.errors)
    units = [
        {"name": p[-1].name, "level": p[-1].level, "under": [n.name for n in p[:-1]]}
        for p in tree.missing.values()
    ]
    report = {
        "rows": entries,
        "total": len(rows),
        "errors": failed,
        "units_to_create": units,
        "administrators": [row.full_name for row in rows if row.role == "admin"],
    }
    if failed:
        return report, []
    requests: list = [ImportUnit(kind="import_unit", path=path) for path in tree.missing.values()]
    requests += [_person(row, paths[row.line], with_passwords) for row in rows]
    return report, requests


def preview(db: Session, actor: Actor, settings: Settings, data: bytes) -> dict:
    service.authorize(db, actor, settings)
    report, requests = review(db, data, settings, service.Deadline(db, settings))
    if requests:
        report["plan"] = bulk.preview(db, actor, settings, bulk.BulkPreview(requests=requests))
    else:
        report["plan"] = None
    return report


def apply(
    db: Session, actor: Actor, settings: Settings, data: bytes, digest: str, reason: str, hub: Hub
) -> dict:
    service.authorize(db, actor, settings)
    report, requests = review(db, data, settings, service.Deadline(db, settings), with_passwords=True)
    if report["errors"]:
        raise Invalid("import_has_errors", "Fix the rows with problems and review the file again.")
    try:
        body = bulk.BulkApply(requests=requests, digest=digest, revisions={}, reason=reason)
    except ValidationError:
        raise Invalid(
            "invalid_request", "Review the file again and give a reason of at least 3 characters."
        ) from None
    return bulk.apply(db, actor, settings, body, hub)
