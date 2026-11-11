"""Isolate pre-staff migration scenarios without weakening their original guards."""

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text


def downgrade_legacy(config: Config, revision: str) -> None:
    """Remove only synthetic P1 and A3 records before exercising an older downgrade guard.

    Login now records a staff date and an activity day, which correctly block dropping
    staff columns and usage history. These older tests exercise other data guards; they
    need a reconstructible staff fixture and no usage history so their original guards are
    reached. P1 and A3 guard tests never use this helper.
    """
    engine = create_engine(config.attributes["database_url"])
    try:
        with engine.begin() as db:
            db.execute(text("DELETE FROM activity_days"))
            db.execute(text("DELETE FROM metric_samples"))
            db.execute(text("DELETE FROM ops_events"))
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
