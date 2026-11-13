"""Find units of the organisation by name along a Group, Division, Section path."""

import unicodedata
import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Workspace
from .import_requests import PathNode
from .plan import Blocker


def fold(name: str) -> str:
    return unicodedata.normalize("NFKC", name).casefold()


@dataclass
class Found:
    """The units of a path that already exist (``None`` from the first missing one on)."""

    units: list[Workspace | None]
    blockers: list[Blocker]

    @property
    def home(self) -> Workspace | None:
        return self.units[-1]


def organisation_root(db: Session) -> Workspace:
    root = db.scalar(select(Workspace).where(Workspace.kind == "org", Workspace.parent_id.is_(None)))
    if root is None:
        raise LookupError("The organisation has no top unit.")
    return root


def children(db: Session) -> dict[tuple[uuid.UUID, str], list[Workspace]]:
    index: dict[tuple[uuid.UUID, str], list[Workspace]] = {}
    for unit in db.scalars(
        select(Workspace).where(Workspace.kind == "org", Workspace.parent_id.is_not(None))
    ):
        index.setdefault((unit.parent_id, fold(unit.name)), []).append(unit)
    return index


def find(db: Session, path: list[PathNode]) -> Found:
    """Match each name case-insensitively among the children of the unit above; never across parents."""
    index = children(db)
    parent = organisation_root(db)
    units: list[Workspace | None] = []
    blockers: list[Blocker] = []
    for node in path:
        matches = index.get((parent.id, fold(node.name)), []) if parent is not None else []
        if len(matches) > 1:
            blockers.append(
                Blocker("unit_ambiguous", f"More than one unit under {parent.name} is called {node.name}.")
            )
            matches = []
        unit = matches[0] if matches else None
        if unit is not None and unit.archived:
            blockers.append(
                Blocker("unit_unavailable", f"{node.name} is closed. Reopen it or use another name.")
            )
        elif unit is not None and unit.level not in (None, node.level):
            blockers.append(
                Blocker("unit_level", f"{node.name} already exists as a {unit.level}, not a {node.level}.")
            )
        units.append(unit)
        parent = unit
    return Found(units, blockers)
