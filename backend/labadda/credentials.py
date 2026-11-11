"""Shared transactional activation/reset issuance; raw tokens are never persisted."""

from datetime import timedelta

from sqlalchemy.orm import Session

from .config import Settings
from .models import CredentialToken, User
from .security import digest, new_token, utcnow


def issue_credential(
    db: Session, user: User, purpose: str, actor: User | None, settings: Settings
) -> tuple[str, CredentialToken]:
    """Issue a one-time activation/reset credential inside the caller's transaction."""
    token = new_token()
    cred = CredentialToken(
        user_id=user.id,
        token_hash=digest(token),
        purpose=purpose,
        expires_at=utcnow() + timedelta(hours=settings.activation_hours),
        created_by=getattr(actor, "id", None),
    )
    db.add(cred)
    return token, cred
