"""Request dependencies: database session, settings, authenticated actor."""

from __future__ import annotations

import uuid
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from datetime import timedelta
from urllib.parse import urlsplit

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from . import policy
from .config import Settings
from .errors import Forbidden, NotFound, Unauthenticated
from .metrics.activity import ACTIVITY
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
    else:
        if now - sess.last_seen_at > timedelta(minutes=1):
            sess.last_seen_at = now
            db.commit()
        # Board-only panels stay outside people activity (AD-08); only normal sessions count.
        ACTIVITY.record(db, user.id, settings, now=now)
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


def _console_actor(request: Request, db: Session = Depends(get_db)) -> Actor:
    """Reject panel intent before normal-session CSRF or idle-time processing."""
    if request.headers.get(PANEL_HEADER):
        raise Unauthenticated()
    return current_actor(request, db)


def console_member(
    request: Request, actor: Actor = Depends(_console_actor), db: Session = Depends(get_db)
) -> Actor:
    """Anyone who may open at least one console section; each page then checks its own section."""
    if request.headers.get(PANEL_HEADER) or actor.is_panel:
        raise Unauthenticated()
    if not policy.console_sections(db, actor.user):
        raise Forbidden("admin_required", "Administrator access is required.")
    return actor


def _unit_admin_section(db: Session, user: User, section: str) -> bool:
    return section in policy.UNIT_ADMIN_SECTIONS and policy.is_unit_admin(db, user)


def require_console(
    section: str, *, admin_only: bool = False, unit_admin: bool = False
) -> Callable[..., Actor]:
    """Gate console requests without widening existing administrative rights.

    ``unit_admin`` lets a current unit administrator in, for the people and organisation endpoints
    that apply their branch scope themselves. Everything else stays for site administrators.
    """
    if section not in policy.CONSOLE_SECTIONS:
        raise ValueError("Unknown console section")

    def authorized(
        request: Request, actor: Actor = Depends(_console_actor), db: Session = Depends(get_db)
    ) -> Actor:
        if request.headers.get(PANEL_HEADER) or actor.is_panel:
            raise Unauthenticated()
        if actor.user.is_admin:
            return actor
        if unit_admin and not admin_only and _unit_admin_section(db, actor.user, section):
            return actor
        if admin_only or section not in policy.READER_SECTIONS or request.method not in {"GET", "HEAD"}:
            raise Forbidden("admin_required", "Administrator access is required.")
        if section not in policy.console_sections(db, actor.user):
            raise Forbidden("usage_read_required", "Operational read access is required.")
        return actor

    return authorized
