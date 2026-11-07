"""Password hashing, opaque tokens, sessions and rate limits."""

from __future__ import annotations

import hashlib
import secrets
import threading
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from sqlalchemy import update
from sqlalchemy.orm import Session

from .config import Settings
from .models import AuthSession, User

_hasher = PasswordHasher()
# Used to equalize timing when the username is unknown.
_DUMMY_HASH = _hasher.hash("labadda-dummy-password")

MIN_PASSWORD_LENGTH = 10


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(stored: str | None, password: str) -> bool:
    try:
        return _hasher.verify(stored or _DUMMY_HASH, password) and stored is not None
    except (VerificationError, InvalidHashError):
        return False


def new_token() -> str:
    return secrets.token_urlsafe(32)


def digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def create_session(db: Session, user: User, settings: Settings, kind: str = "normal") -> tuple[str, AuthSession]:
    token = new_token()
    now = utcnow()
    sess = AuthSession(
        id=digest(token),
        user_id=user.id,
        csrf_token=secrets.token_urlsafe(24),
        kind=kind,
        last_seen_at=now,
        expires_at=now + timedelta(hours=settings.session_absolute_hours),
    )
    db.add(sess)
    return token, sess


def session_valid(sess: AuthSession, settings: Settings, now: datetime | None = None) -> bool:
    now = now or utcnow()
    if sess.revoked_at is not None or sess.expires_at <= now:
        return False
    if sess.kind == "board":
        return now - sess.last_seen_at <= timedelta(seconds=settings.panel_idle_seconds)
    return now - sess.last_seen_at <= timedelta(minutes=settings.session_idle_minutes)


def revoke_user_sessions(db: Session, user_id) -> None:
    db.execute(
        update(AuthSession)
        .where(AuthSession.user_id == user_id, AuthSession.revoked_at.is_(None))
        .values(revoked_at=utcnow())
    )


class RateLimiter:
    """Sliding-window limiter for a single-process deployment."""

    def __init__(self) -> None:
        self._events: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def hit(self, key: str, limit: int, window: int) -> bool:
        now = time.monotonic()
        with self._lock:
            q = self._events[key]
            while q and now - q[0] > window:
                q.popleft()
            if len(q) >= limit:
                return False
            q.append(now)
            return True

    def reset(self) -> None:
        with self._lock:
            self._events.clear()


login_limiter = RateLimiter()
