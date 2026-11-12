"""Issue a fresh one-time activation code for an account that has not been activated yet."""

import uuid

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from .. import audit
from ..config import Settings
from ..credentials import issue_credential
from ..deps import Actor
from ..errors import Conflict, NotFound
from ..models import CredentialToken, User
from ..security import utcnow
from ..serialize import iso
from .service import authorize


def reissue(db: Session, actor: Actor, settings: Settings, person_id: uuid.UUID, reason: str) -> dict:
    """Withdraw unused codes, issue a new one and audit it in one transaction (PO-09)."""
    try:
        user = authorize(db, actor, settings)
        # Account row first, then its tokens: the same order as redemption in /auth/activate.
        person = db.scalar(
            select(User)
            .where(User.id == person_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if person is None:
            raise NotFound()
        if person.status != "invited" or not person.must_set_password:
            raise Conflict(
                "not_invited", "Only people who have not activated their account can get a new code."
            )
        now = utcnow()
        db.execute(
            update(CredentialToken)
            .where(CredentialToken.user_id == person.id, CredentialToken.used_at.is_(None))
            .values(used_at=now)
        )
        code, credential = issue_credential(db, person, "activation", user, settings)
        audit.record(
            db,
            actor=user,
            action="identity.activation_reissued",
            scope_type="identity",
            target_id=person.id,
            reason=reason,
        )
        db.commit()
    except Exception:
        db.rollback()
        raise
    return {"person_id": str(person.id), "code": code, "expires_at": iso(credential.expires_at)}
