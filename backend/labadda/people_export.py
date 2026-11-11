"""Bounded formula-safe directory reports; no private content, contacts or stored files."""

import csv
import io
import unicodedata

from sqlalchemy.orm import Session

from .errors import Invalid
from .people_directory import DirectoryFilters, directory_query, person_json

EXPORT_LIMIT = 10_000
COLUMNS = ("display_name", "username", "employee_no", "designation", "home_unit", "status", "last_seen_on")


def safe_cell(value: str | None) -> str:
    """Prevent spreadsheet interpretation, including control/space-prefixed formulas."""
    value = value or ""
    candidate = value
    while candidate and (candidate[0].isspace() or unicodedata.category(candidate[0]) in {"Cc", "Cf"}):
        candidate = candidate[1:]
    if unicodedata.normalize("NFKC", candidate).startswith(("=", "+", "-", "@")) or value.startswith(
        ("\t", "\r", "\n")
    ):
        return "'" + value
    return value


def prepare_csv(db: Session, filters: DirectoryFilters) -> dict:
    """Materialize at most the report cap before any response bytes are delivered."""
    rows = db.execute(
        directory_query(db, filters).limit(EXPORT_LIMIT + 1).execution_options(populate_existing=True)
    ).all()
    if len(rows) > EXPORT_LIMIT:
        raise Invalid("export_limit", "Too many people for one report. Narrow the filters and export again.")
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(COLUMNS)
    for person, unit in rows:
        record = person_json(person, unit)
        record["home_unit"] = unit.name if unit else None
        writer.writerow([safe_cell(record[column]) for column in COLUMNS])
    return {"body": "\ufeff" + output.getvalue(), "rows": len(rows)}
