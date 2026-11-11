"""A signed-in person's own record, password and sessions (P8)."""

import uuid

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import account, audit
from ..config import Settings
from ..deps import PANEL_HEADER, Actor, current_actor, get_db, get_settings
from ..errors import Conflict, Invalid, NotFound, TooMany, Unauthenticated
from ..models import AuthSession, User
from ..security import (
    MIN_PASSWORD_LENGTH,
    hash_password,
    login_limiter,
    revoke_user_sessions,
    utcnow,
    verify_password,
)

router = APIRouter(prefix="/me", tags=["me"])


class PasswordChange(BaseModel):
    model_config = ConfigDict(extra="forbid")
    current_password: str = Field(min_length=1, max_length=256)
    new_password: str = Field(min_length=1, max_length=256)


def own_actor(request: Request, db: Session = Depends(get_db)) -> Actor:
    """Normal sessions only; a panel-marked request never reaches personal account data."""
    if request.headers.get(PANEL_HEADER):
        raise Unauthenticated()
    return current_actor(request, db)


@router.get("/profile")
def get_profile(actor: Actor = Depends(own_actor), db: Session = Depends(get_db)) -> dict:
    return account.own_profile(db, actor.user.id)


@router.post("/password")
def change_password(
    body: PasswordChange,
    request: Request,
    actor: Actor = Depends(own_actor),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> dict:
    """Replace the password, end every other sign-in at once and keep this one."""
    if not login_limiter.hit(
        f"password:{actor.user.id}", settings.login_attempts_per_window, settings.login_window_seconds
    ):
        raise TooMany()
    user = db.get(User, actor.user.id, with_for_update=True)
    if not verify_password(user.password_hash, body.current_password):
        audit.record(
            db,
            actor=user,
            action="auth.password_changed",
            scope_type="identity",
            target_id=user.id,
            outcome="denied",
        )
        db.commit()
        raise Invalid("invalid_credentials", "Your current password is not correct.")
    if len(body.new_password) < MIN_PASSWORD_LENGTH:
        raise Invalid("weak_password", f"Use at least {MIN_PASSWORD_LENGTH} characters.")
    if body.new_password == body.current_password:
        raise Invalid("password_unchanged", "Choose a password you have not used just now.")
    user.password_hash = hash_password(body.new_password)
    ended = revoke_user_sessions(db, user.id, keep=actor.session.id)
    audit.record(
        db,
        actor=user,
        action="auth.password_changed",
        scope_type="identity",
        target_id=user.id,
        sessions_ended=ended,
    )
    db.commit()
    request.app.state.hub.revalidate_user(user.id)
    return {"ok": True, "sessions_ended": ended}


@router.get("/sessions")
def list_sessions(
    actor: Actor = Depends(own_actor),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> dict:
    return {"items": account.own_sessions(db, actor.user.id, actor.session.id, settings)}


@router.delete("/sessions/{session_id}")
def end_session(
    session_id: uuid.UUID,
    request: Request,
    actor: Actor = Depends(own_actor),
    db: Session = Depends(get_db),
) -> dict:
    """End one of the caller's other sessions; anyone else's session is a uniform 404."""
    target = db.scalar(
        select(AuthSession)
        .where(
            AuthSession.public_id == session_id,
            AuthSession.user_id == actor.user.id,
            AuthSession.kind == "normal",
            AuthSession.revoked_at.is_(None),
        )
        .with_for_update()
    )
    if target is None:
        raise NotFound()
    if target.id == actor.session.id:
        raise Conflict("current_session", "Use Sign out to end the session you are using.")
    target.revoked_at = utcnow()
    target.end_reason = "signed_out_by_owner"
    audit.record(
        db, actor=actor.user, action="auth.session_ended", scope_type="identity", target_id=actor.user.id
    )
    db.commit()
    request.app.state.hub.revalidate_user(actor.user.id)
    return {"ok": True}
