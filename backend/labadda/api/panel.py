"""Board-only touch-panel sessions (S3 "Live whiteboard and touch", T11).

A signed-in user creates a short-lived, single-use pairing code for one
workspace board. Entering the code on the shared panel starts a board-only
session with a separately named cookie. That session can use only the selected
board and the images embedded on it. It locks after a short idle period,
has a hard expiry, and records who started and how it ended.
"""

from __future__ import annotations

import secrets
import uuid
from datetime import timedelta

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import audit, policy
from ..config import Settings
from ..deps import Actor, current_actor, get_db, get_settings, origin_allowed, panel_actor
from ..errors import Forbidden, Invalid, NotFound, TooMany
from ..models import AuthSession, PanelPairing, User
from ..security import create_session, digest, login_limiter, utcnow
from ..serialize import iso

router = APIRouter(prefix="/panel", tags=["panel"])
CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no 0/O or 1/I
END_REASONS = {"ended", "idle_lock"}


class PairingBody(BaseModel):
    workspace_id: uuid.UUID


class ClaimBody(BaseModel):
    code: str = Field(min_length=6, max_length=16)


class EndBody(BaseModel):
    reason: str = "ended"


def _normalize(code: str) -> str:
    return "".join(ch for ch in code.upper() if ch.isalnum())


@router.post("/pairings", status_code=201)
def create_pairing(
    body: PairingBody,
    actor: Actor = Depends(current_actor),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    access = policy.require_read(db, actor.user, body.workspace_id)
    code = "".join(secrets.choice(CODE_ALPHABET) for _ in range(8))
    pairing = PanelPairing(
        code_hash=digest(code),
        user_id=actor.id,
        workspace_id=body.workspace_id,
        expires_at=utcnow() + timedelta(seconds=settings.panel_pairing_seconds),
    )
    db.add(pairing)
    audit.record(
        db,
        actor=actor.user,
        action="panel.pairing_created",
        scope_type="workspace",
        scope_id=body.workspace_id,
    )
    db.commit()
    return {
        "code": f"{code[:4]}-{code[4:]}",
        "expires_at": iso(pairing.expires_at),
        "workspace": {"id": str(access.workspace.id), "name": access.workspace.name},
    }


def _set_cookie(response: Response, token: str, settings: Settings) -> None:
    response.set_cookie(
        settings.panel_cookie_name,
        token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="strict",
        path=settings.cookie_path,
        max_age=settings.panel_absolute_minutes * 60,
    )


def _end(db: Session, sess: AuthSession, reason: str) -> None:
    if sess.revoked_at is None:
        sess.revoked_at = utcnow()
        sess.end_reason = reason


@router.post("/claim")
def claim(
    body: ClaimBody,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    if not origin_allowed(request.headers.get("origin"), request.headers.get("host"), settings):
        raise Forbidden("bad_origin", "Request origin is not trusted.")
    client = request.client.host if request.client else "unknown"
    if not login_limiter.hit(
        f"panel:{client}", settings.login_attempts_per_window, settings.login_window_seconds
    ):
        raise TooMany()
    invalid = Invalid(
        "code_invalid", "That code is not valid or has expired. Create a new one on your computer."
    )
    pairing = db.scalar(
        select(PanelPairing).where(PanelPairing.code_hash == digest(_normalize(body.code))).with_for_update()
    )
    now = utcnow()
    if pairing is None or pairing.used_at is not None or pairing.expires_at <= now:
        raise invalid
    user = db.get(User, pairing.user_id)
    if user is None or not user.is_active or policy.resolve(db, user, pairing.workspace_id) is None:
        raise invalid
    pairing.used_at = now
    # Replace any panel session this browser already holds.
    old_token = request.cookies.get(settings.panel_cookie_name)
    if old_token:
        old = db.get(AuthSession, digest(old_token))
        if old is not None and old.kind == "board":
            _end(db, old, "replaced")
    token, sess = create_session(db, user, settings, kind="board")
    sess.workspace_id = pairing.workspace_id
    sess.expires_at = now + timedelta(minutes=settings.panel_absolute_minutes)
    audit.record(
        db,
        actor=user,
        action="panel.start",
        scope_type="workspace",
        scope_id=pairing.workspace_id,
        target_id=user.id,
    )
    db.commit()
    _set_cookie(response, token, settings)
    return _session_json(db, user, sess, settings)


def _session_json(db: Session, user: User, sess: AuthSession, settings: Settings) -> dict:
    access = policy.resolve(db, user, sess.workspace_id)
    if access is None:
        raise NotFound()
    return {
        "user": {"id": str(user.id), "display_name": user.display_name},
        "workspace": {
            "id": str(access.workspace.id),
            "name": access.workspace.name,
            "can_write": access.can_write,
            "archived": access.workspace.archived,
        },
        "csrf_token": sess.csrf_token,
        "expires_at": iso(sess.expires_at),
        "idle_seconds": settings.panel_idle_seconds,
        "instance": settings.instance,
    }


@router.get("/session")
def panel_session(
    actor: Actor = Depends(panel_actor),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    return _session_json(db, actor.user, actor.session, settings)


@router.post("/activity")
def activity(actor: Actor = Depends(panel_actor), settings: Settings = Depends(get_settings)):
    """Interaction heartbeat from the panel; the dependency already refreshed the idle clock."""
    return {"ok": True, "idle_seconds": settings.panel_idle_seconds}


@router.post("/end")
def end(
    body: EndBody,
    request: Request,
    response: Response,
    *,
    actor: Actor = Depends(panel_actor),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    reason = body.reason if body.reason in END_REASONS else "ended"
    sess = db.get(AuthSession, actor.session.id)
    _end(db, sess, reason)
    audit.record(
        db,
        actor=actor.user,
        action="panel.lock" if reason == "idle_lock" else "panel.end",
        scope_type="workspace",
        scope_id=sess.workspace_id,
        target_id=actor.id,
    )
    db.commit()
    response.delete_cookie(settings.panel_cookie_name, path=settings.cookie_path)
    request.app.state.hub.revalidate_user(actor.id)
    return {"ok": True}
