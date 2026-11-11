"""P1 formula-safe bounded staff reports and current-authority delivery."""

import csv
import io
from unittest.mock import patch

import pytest
from sqlalchemy import select

from labadda import people_export
from labadda.api import people as people_api
from labadda.models import AuditEvent, User


@pytest.mark.parametrize(
    "value", ["=1+1", "+1", "-1", "@SUM(A1)", "  =1", "\tplain", "\n=1", "\ufeff=1", "＝1"]
)
def test_formula_prefixes_are_escaped(value):
    assert people_export.safe_cell(value) == "'" + value
    assert people_export.safe_cell("Researcher") == "Researcher"
    assert people_export.safe_cell(None) == ""


def test_csv_matches_filters_and_audits_without_search_terms(as_user, ids, db_factory):
    with db_factory() as db:
        person = db.get(User, ids["users"]["ben"])
        person.display_name = "=Synthetic staff"
        person.contact_email = "private-staff@research.example"
        db.commit()
    response = as_user("admin").get("/admin/people/export.csv?q=synthetic")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert response.headers["content-disposition"] == 'attachment; filename="people.csv"'
    rows = list(csv.DictReader(io.StringIO(response.content.decode("utf-8-sig"))))
    assert len(rows) == 1 and rows[0]["display_name"] == "'=Synthetic staff"
    assert "private-staff" not in response.text
    with db_factory() as db:
        record = db.scalars(select(AuditEvent).where(AuditEvent.action == "people.export")).one()
        assert record.detail == {"rows": "1"}
        assert "synthetic" not in str(record.detail)


def test_report_cap_returns_guidance_without_partial_success(as_user, db_factory):
    with patch.object(people_export, "EXPORT_LIMIT", 1):
        response = as_user("admin").get("/admin/people/export.csv")
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "export_limit"
    with db_factory() as db:
        assert db.scalar(select(AuditEvent.id).where(AuditEvent.action == "people.export")) is None


def test_export_rechecks_after_audit_commit(as_user, ids, db_factory):
    admin = as_user("admin")
    original = people_api.refresh_authority
    calls = 0

    def revoke_at_delivery(request, db):
        nonlocal calls
        calls += 1
        if calls == 3:
            with db_factory() as writer:
                writer.get(User, ids["users"]["admin"]).is_admin = False
                writer.commit()
        return original(request, db)

    with patch.object(people_api, "refresh_authority", side_effect=revoke_at_delivery):
        response = admin.get("/admin/people/export.csv")
    assert response.status_code == 403
    assert not response.headers.get("content-disposition")
    assert "employee_no" not in response.text


def test_export_rejects_members(as_user):
    assert as_user("ben").get("/admin/people/export.csv").status_code == 403
