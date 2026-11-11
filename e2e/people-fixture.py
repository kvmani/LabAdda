"""Staff directory stress data restricted to the disposable local browser databases."""

from datetime import date

from sqlalchemy import select
from sqlalchemy.engine import make_url

from labadda import audit, people
from labadda.config import load_settings
from labadda.db import session_factory
from labadda.models import User


def prepare() -> None:
    """Add fictional staff without touching retained demos or operator databases."""
    settings = load_settings()
    url = make_url(settings.database_url)
    assert settings.environment == "test" and url.host == "localhost"
    assert url.database in {"labadda_e2e_root", "labadda_e2e_prefix"}
    with session_factory(settings.database_url)() as db:
        admin = db.scalar(select(User).where(User.username == "admin"))
        ben = db.scalar(select(User).where(User.username == "ben"))
        assert admin is not None and ben is not None
        ben.employee_no = "NW-100"
        ben.designation = "Research Officer D"
        ben.contact_email = "ben@research.example"
        ben.contact_phone = "214"
        ben.joined_on = date(2023, 7, 3)
        for index in range(55):
            username = f"directory{index:02}"
            if db.scalar(select(User.id).where(User.username == username)) is not None:
                continue
            person = User(
                username=username,
                display_name=f"Directory Researcher {index:02}",
                employee_no=f"TEST-{index:03}",
                home_workspace_id=ben.home_workspace_id,
                password_hash=None,
            )
            people.set_status(person, "invited")
            db.add(person)
        if db.scalar(select(User.id).where(User.username == "reviewadmin")) is None:
            reviewer = User(
                username="reviewadmin",
                display_name="Review Administrator",
                is_admin=True,
                password_hash=admin.password_hash,
                must_set_password=False,
            )
            people.set_status(reviewer, "active")
            db.add(reviewer)
        audit.record(
            db,
            actor=admin,
            action="identity.update",
            scope_type="identity",
            target_id=ben.id,
            reason="Synthetic staff review",
            private_marker="PRIVATE-AUDIT-DETAIL-MUST-NOT-APPEAR",
        )
        db.commit()
    print("Synthetic staff directory prepared")


if __name__ == "__main__":
    prepare()
