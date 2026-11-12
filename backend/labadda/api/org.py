"""Administrator-only organisation chart data; names, roles and counts, never content."""

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from .. import org_tree
from ..deps import Actor, get_db, require_console
from .people import read_metadata

router = APIRouter(prefix="/admin/org", tags=["organisation"])
console_people = require_console("people")


@router.get("/tree")
def get_tree(request: Request, actor: Actor = Depends(console_people), db: Session = Depends(get_db)) -> dict:
    """Units with Head, stewards and people counts, and the projects and groups beside them."""
    return read_metadata(request, db, lambda: org_tree.tree(db))
