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


def _json(row):
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
    row = db.get(NotificationPreference, user.id)
    if body.revision != (row.revision if row else 0):
        raise Conflict(
            "revision_conflict", "Your alert settings changed. Reload the current choices before saving."
        )
    values = body.model_dump(exclude={"revision"})
    if row is None:
        row = NotificationPreference(user_id=user.id, revision=1, **values)
        db.add(row)
    else:
        for name, value in values.items():
            setattr(row, name, value)
        row.revision += 1
    lock_identity(db, actor, get_settings(request))
    db.commit()
    return _json(row)
