"""Request dependencies: database session, settings, authenticated actor."""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import timedelta
from urllib.parse import urlsplit

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from .config import Settings
from .errors import Forbidden, NotFound, Unauthenticated
from .models import AuthSession, User
from .security import digest, session_valid, utcnow

UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_db(request: Request) -> Iterator[Session]:
    db = request.app.state.session_factory()
    try:
        yield db
    finally:
        db.close()


@dataclass
class Actor:
    user: User
    session: AuthSession

    @property
    def id(self):
        return self.user.id

    @property
    def is_panel(self) -> bool:
        return self.session.kind == "board"


def origin_allowed(origin: str | None, host: str | None, settings: Settings) -> bool:
    """Allow absent Origin (same-origin non-browser clients) or a same-host/trusted origin."""
    if not origin:
        return True
    origin = origin.rstrip("/")
    if origin in settings.trusted_origins:
        return True
    parts = urlsplit(origin)
    return bool(host) and parts.netloc == host


PANEL_HEADER = "x-labadda-panel"


def _load_actor(request: Request, db: Session, settings: Settings, kind: str) -> Actor:
    cookie = settings.panel_cookie_name if kind == "board" else settings.cookie_name
    token = request.cookies.get(cookie)
    if not token:
        raise Unauthenticated()
    sess = db.get(AuthSession, digest(token))
    if sess is None or not session_valid(sess, settings):
        raise Unauthenticated("session_expired", "Your session has ended. Sign in again.")
    user = db.get(User, sess.user_id)
    if user is None or not user.is_active:
        raise Unauthenticated()
    if sess.kind != kind:
        # A board-only session can never act as a normal session, and vice versa.
        raise Unauthenticated("session_scope", "This session cannot open that page.")
    if request.method in UNSAFE_METHODS:
        if not origin_allowed(request.headers.get("origin"), request.headers.get("host"), settings):
            raise Forbidden("bad_origin", "Request origin is not trusted.")
        if request.headers.get("x-csrf-token") != sess.csrf_token:
            raise Forbidden("csrf_failed", "Security token missing or stale. Reload the page.")
    now = utcnow()
    if kind == "board":
        # Panel idle time counts from the last interaction (any write or activity ping), not from reads.
        if request.method in UNSAFE_METHODS:
            sess.last_seen_at = now
            db.commit()
    elif now - sess.last_seen_at > timedelta(minutes=1):
        sess.last_seen_at = now
        db.commit()
    return Actor(user=user, session=sess)


def current_actor(request: Request, db: Session = Depends(get_db)) -> Actor:
    return _load_actor(request, db, get_settings(request), "normal")


def panel_actor(request: Request, db: Session = Depends(get_db)) -> Actor:
    """A board-only touch-panel session (separately named cookie)."""
    return _load_actor(request, db, get_settings(request), "board")


def board_actor(workspace_id: uuid.UUID, request: Request, db: Session = Depends(get_db)) -> Actor:
    """Normal session, or a panel session bound to exactly this workspace's board.

    The panel client marks its requests with ``X-LabAdda-Panel`` so a kiosk never
    falls back to a desktop cookie. A panel session for another board gets the
    uniform 404.
    """
    if request.headers.get(PANEL_HEADER):
        actor = panel_actor(request, db)
        if actor.session.workspace_id != workspace_id:
            raise NotFound()
        return actor
    return current_actor(request, db)


def require_admin(actor: Actor = Depends(current_actor)) -> Actor:
    if not actor.user.is_admin:
        raise Forbidden("admin_required", "Administrator access is required.")
    return actor
