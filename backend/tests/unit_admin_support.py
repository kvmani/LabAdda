"""Shared fictional setup for unit-administrator tests (P7)."""

from sqlalchemy import select

from labadda.models import UnitAdminGrant
from labadda.security import utcnow
from tests.test_changes_authority import change
from tests.test_changes_edit import reviewed


def appoint(db_factory, ids, username, unit, **values):
    """Record an appointment directly, as an earlier reviewed change would have."""
    with db_factory() as db:
        db.add(
            UnitAdminGrant(
                user_id=ids["users"][username],
                workspace_id=ids["workspaces"][unit],
                granted_by=ids["users"]["admin"],
                **values,
            )
        )
        db.commit()


def withdraw(db_factory, ids, username, unit):
    with db_factory() as db:
        row = db.scalar(
            select(UnitAdminGrant).where(
                UnitAdminGrant.user_id == ids["users"][username],
                UnitAdminGrant.workspace_id == ids["workspaces"][unit],
                UnitAdminGrant.revoked_at.is_(None),
            )
        )
        row.revoked_at = utcnow()
        db.commit()


def preview(api, request):
    return api.post("/admin/changes/preview", json=request)


def apply_reviewed(api, request, expect=200):
    """Review then apply; returns the apply response."""
    confirmation = reviewed(api, request)
    response = api.post("/admin/changes/apply", json=confirmation)
    assert response.status_code == expect, response.text
    return response


def grant_request(ids, person, unit, kind="unit_admin_grant"):
    return change(ids, kind, person_id=person, unit_id=unit)
