"""Refresh and serialize authenticated mutation authority with identity changes."""

from sqlalchemy import select

from .errors import Unauthenticated
from .models import AuthSession, User
from .security import session_valid


def lock_identity(db, actor, settings):
    # User → session order matches identity deactivation/reset. NO KEY UPDATE
    # excludes role/password writes while permitting foreign-key audit inserts.
    user = db.scalar(
        select(User)
        .where(User.id == actor.id)
        .with_for_update(key_share=True)
        .execution_options(populate_existing=True)
    )
    session = db.scalar(
        select(AuthSession)
        .where(AuthSession.id == actor.session.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if (
        user is None
        or not user.is_active
        or session is None
        or session.user_id != user.id
        or session.kind != "normal"
        or not session_valid(session, settings)
    ):
        raise Unauthenticated()
    return user
