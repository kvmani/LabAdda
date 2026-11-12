"""Administrator-only organisation chart data; names, roles and counts, never content."""

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from .. import org_tree
from ..deps import Actor, get_db, get_settings, require_console
from ..overview import people_attention
from ..security import utcnow
from .people import read_metadata

router = APIRouter(prefix="/admin/org", tags=["organisation"])
console_people = require_console("people", unit_admin=True)
console_people_admin = require_console("people")


@router.get("/tree")
def get_tree(request: Request, actor: Actor = Depends(console_people), db: Session = Depends(get_db)) -> dict:
    """Units with Head, stewards and people counts, and the projects and groups beside them."""
    return read_metadata(request, db, actor, lambda scope: org_tree.tree(db, scope))


@router.get("/attention")
def get_attention(
    request: Request, actor: Actor = Depends(console_people_admin), db: Session = Depends(get_db)
) -> dict:
    """People items that need a site administrator, each with the page that fixes it; no content.

    The items are computed over the whole organisation, so unit administrators do not get them.
    """
    settings = get_settings(request)
    return read_metadata(
        request, db, actor, lambda _: {"items": people_attention.people_entries(db, settings, utcnow())}
    )


@router.get("/unit-admins")
def get_unit_administrators(
    request: Request, actor: Actor = Depends(console_people_admin), db: Session = Depends(get_db)
) -> dict:
    """Who has been appointed unit administrator of which unit; site administrators only."""
    return read_metadata(request, db, actor, lambda _: org_tree.unit_administrators(db))
