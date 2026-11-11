"""Sign-in, sign-out, activation and session status (S2)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import audit, metrics, people
from ..config import Settings
from ..deps import Actor, current_actor, get_db, get_settings, origin_allowed
from ..errors import Forbidden, Invalid, TooMany, Unauthenticated
from ..models import AuthSession, CredentialToken, User
from ..security import (
    MIN_PASSWORD_LENGTH,
    create_session,
    digest,
    hash_password,
    login_limiter,
    revoke_user_sessions,
    utcnow,
    verify_password,
)
from ..serialize import user_brief

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginBody(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=256)


class ActivateBody(BaseModel):
    token: str = Field(min_length=10, max_length=128)
    password: str = Field(min_length=1, max_length=256)


class PasswordBody(BaseModel):
    current_password: str = Field(max_length=256)
    new_password: str = Field(max_length=256)


def _check_origin(request: Request, settings: Settings) -> None:
    if not origin_allowed(request.headers.get("origin"), request.headers.get("host"), settings):
        raise Forbidden("bad_origin", "Request origin is not trusted.")


def _set_cookie(response: Response, token: str, settings: Settings) -> None:
    response.set_cookie(
        settings.cookie_name,
        token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="strict",
        path=settings.cookie_path,
        max_age=settings.session_absolute_hours * 3600,
    )


def _validate_password(password: str) -> None:
    if len(password) < MIN_PASSWORD_LENGTH:
        raise Invalid("weak_password", f"Use at least {MIN_PASSWORD_LENGTH} characters.")


def session_payload(user: User, sess: AuthSession, settings: Settings) -> dict:
    return {
        "user": {
            **user_brief(user),
            "is_admin": user.is_admin,
            "home_workspace_id": str(user.home_workspace_id) if user.home_workspace_id else None,
        },
        "csrf_token": sess.csrf_token,
        "session_kind": sess.kind,
        "expires_at": sess.expires_at.isoformat(),
        "instance": settings.instance,
        "timezone": settings.timezone,
        "limits": {
            "max_attachments": settings.max_attachments,
            "max_attachment_bytes": settings.max_attachment_bytes,
        },
    }


@router.post("/login")
def login(
    body: LoginBody,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    _check_origin(request, settings)
    username = body.username.strip().lower()
    client = request.client.host if request.client else "unknown"
    if not login_limiter.hit(
        f"login:{username}", settings.login_attempts_per_window, settings.login_window_seconds
    ) or not login_limiter.hit(
        f"ip:{client}", settings.login_attempts_per_window * 5, settings.login_window_seconds
    ):
        raise TooMany()
    user = db.scalar(select(User).where(User.username == username))
    ok = verify_password(user.password_hash if user else None, body.password)
    if not user or not ok or not user.is_active or user.must_set_password:
        audit.record(
            db,
            actor=user,
            action="auth.login",
            scope_type="identity",
            target_id=user.id if user else None,
            outcome="denied",
        )
        db.commit()
        metrics.count("auth.signin_failed")
        raise Unauthenticated("invalid_credentials", "Username or password is incorrect.")
    people.record_sign_in(db, user, settings)
    token, sess = create_session(db, user, settings)
    audit.record(db, actor=user, action="auth.login", scope_type="identity", target_id=user.id)
    db.commit()
    metrics.count("auth.signin_ok")
    _set_cookie(response, token, settings)
    return session_payload(user, sess, settings)


@router.post("/logout")
def logout(
    request: Request,
    response: Response,
    actor: Actor = Depends(current_actor),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    sess = db.get(AuthSession, actor.session.id)
    sess.revoked_at = utcnow()
    db.commit()
    response.delete_cookie(settings.cookie_name, path=settings.cookie_path)
    return {"ok": True}


@router.get("/session")
def session_status(actor: Actor = Depends(current_actor), settings: Settings = Depends(get_settings)):
    return session_payload(actor.user, actor.session, settings)


@router.post("/activate")
def activate(
    body: ActivateBody,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    """Redeem a one-time activation or reset credential and set a password."""
    _check_origin(request, settings)
    client = request.client.host if request.client else "unknown"
    if not login_limiter.hit(
        f"activate:{client}", settings.login_attempts_per_window, settings.login_window_seconds
    ):
        raise TooMany()
    _validate_password(body.password)
    cred = db.scalar(
        select(CredentialToken).where(CredentialToken.token_hash == digest(body.token)).with_for_update()
    )
    now = utcnow()
    if cred is None or cred.used_at is not None or cred.expires_at <= now:
        raise Invalid(
            "token_invalid",
            "This activation link is invalid or has expired. Ask an administrator for a new one.",
        )
    user = db.get(User, cred.user_id)
    if user is None or not user.is_active:
        raise Invalid(
            "token_invalid",
            "This activation link is invalid or has expired. Ask an administrator for a new one.",
        )
    cred.used_at = now
    user.password_hash = hash_password(body.password)
    status_before = user.status
    user.must_set_password = False
    if user.status == "invited":
        people.set_status(user, "active", effective_on=people.site_date(settings, now=now))
    people.record_sign_in(db, user, settings, now=now)
    revoke_user_sessions(db, user.id)
    token, sess = create_session(db, user, settings)
    audit.record(
        db,
        actor=user,
        action=f"auth.{cred.purpose}_redeemed",
        scope_type="identity",
        target_id=user.id,
        status_before=status_before,
        status_after=user.status,
    )
    db.commit()
    _set_cookie(response, token, settings)
    return session_payload(user, sess, settings)


@router.post("/password")
def change_password(
    body: PasswordBody,
    response: Response,
    actor: Actor = Depends(current_actor),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    user = db.get(User, actor.user.id)
    if not verify_password(user.password_hash, body.current_password):
        raise Invalid("invalid_credentials", "Current password is incorrect.")
    _validate_password(body.new_password)
    user.password_hash = hash_password(body.new_password)
    revoke_user_sessions(db, user.id)
    token, sess = create_session(db, user, settings)
    audit.record(db, actor=user, action="auth.password_changed", scope_type="identity", target_id=user.id)
    db.commit()
    _set_cookie(response, token, settings)
    return session_payload(user, sess, settings)
