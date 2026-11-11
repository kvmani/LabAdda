"""Isolate pre-staff migration scenarios without weakening their original guards."""

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text


def downgrade_legacy(config: Config, revision: str) -> None:
    """Remove only synthetic P1 attributes before exercising an older downgrade guard.

    Login now records a staff date, which correctly blocks dropping staff columns.
    These older tests exercise other data guards; they need a reconstructible staff
    fixture so their original guards are reached. P1 guard tests never use this helper.
    """
    engine = create_engine(config.attributes["database_url"])
    try:
        with engine.begin() as db:
            db.execute(
                text("""
                UPDATE users SET employee_no=NULL, designation=NULL, contact_email=NULL,
                  contact_phone=NULL, status_effective_on=NULL, expected_return_on=NULL,
                  joined_on=NULL, last_seen_on=NULL, revision=1,
                  status=CASE WHEN NOT is_active THEN 'left'
                    WHEN must_set_password THEN 'invited' ELSE 'active' END
            """)
            )
        command.downgrade(config, revision)
    finally:
        engine.dispose()
