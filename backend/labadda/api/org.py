"""Administrator-only organisation chart data; names, roles and counts, never content."""

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from .. import org_tree
from ..deps import Actor, get_db, get_settings, require_console
from ..overview import people_attention
from ..security import utcnow
from .people import read_metadata

router = APIRouter(prefix="/admin/org", tags=["organisation"])
console_people = require_console("people")


@router.get("/tree")
def get_tree(request: Request, actor: Actor = Depends(console_people), db: Session = Depends(get_db)) -> dict:
    """Units with Head, stewards and people counts, and the projects and groups beside them."""
    return read_metadata(request, db, lambda: org_tree.tree(db))


@router.get("/attention")
def get_attention(
    request: Request, actor: Actor = Depends(console_people), db: Session = Depends(get_db)
) -> dict:
    """People items that need an administrator, each with the page that fixes it; no content."""
    settings = get_settings(request)
    return read_metadata(
        request, db, lambda: {"items": people_attention.people_entries(db, settings, utcnow())}
    )
