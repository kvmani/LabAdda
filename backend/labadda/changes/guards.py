"""Metadata-only guards shared by staff-change builders."""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import User
from .plan import Blocker


def unique_employee_number(
    db: Session, value: str | None, person_id: uuid.UUID | None = None
) -> list[Blocker]:
    """Block duplicate employee numbers without exposing the other person's record."""
    if value is None:
        return []
    query = select(User.id).where(User.employee_no == value)
    if person_id is not None:
        query = query.where(User.id != person_id)
    if db.scalar(query.limit(1)) is None:
        return []
    return [Blocker("duplicate_employee", "That employee number is already assigned to another person.")]
