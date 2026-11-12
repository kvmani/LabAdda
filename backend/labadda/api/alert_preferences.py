"""Owner-only revisioned alert controls, no administrator content/settings bypass."""

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from ..deps import Actor, current_actor, get_db, get_settings
from ..errors import Conflict
from ..identity_locks import lock_identity
from ..models import NotificationPreference
from .todos import _actor

router = APIRouter(prefix="/notification-preferences", tags=["notifications"])


class Choices(BaseModel):
    model_config = ConfigDict(extra="forbid")
    mentions: bool = Field(strict=True)
    official_notices: bool = Field(strict=True)
    reminders: bool = Field(strict=True)
    revision: int = Field(ge=0, strict=True)


def _json(row: NotificationPreference | None) -> dict:
    """Serialize saved choices; a user who never saved gets everything on at revision 0."""
    return {
        "mentions": row.mentions if row else True,
        "official_notices": row.official_notices if row else True,
        "reminders": row.reminders if row else True,
        "revision": row.revision if row else 0,
    }


@router.get("")
def preferences(request: Request, actor: Actor = Depends(current_actor), db: Session = Depends(get_db)):
    user = _actor(request, actor, db)
    result = _json(db.get(NotificationPreference, user.id))
    _actor(request, actor, db)
    return result


@router.put("")
def save(
    body: Choices, request: Request, actor: Actor = Depends(current_actor), db: Session = Depends(get_db)
):
    user = _actor(request, actor, db, True)
    saved = db.get(NotificationPreference, user.id)
    saved_revision = saved.revision if saved else 0
    if body.revision != saved_revision:
        raise Conflict(
            "revision_conflict", "Your alert settings changed. Reload the current choices before saving."
        )
    choices = body.model_dump(exclude={"revision"})
    if saved is None:
        saved = NotificationPreference(user_id=user.id, revision=1, **choices)
        db.add(saved)
    else:
        for name, value in choices.items():
            setattr(saved, name, value)
        saved.revision += 1
    lock_identity(db, actor, get_settings(request))
    db.commit()
    return _json(saved)
