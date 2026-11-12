"""Reviewed edits: stale/concurrent plans, atomic audit, denial and metadata isolation."""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import patch

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import OperationalError

from labadda import audit
from labadda.changes import service
from labadda.changes.kinds import edit_person
from labadda.models import AuditEvent, User
from tests.test_capabilities import grant
from tests.test_panel import PANEL, pair


def edit(ids, **fields):
    """Build a fictional, explicitly selected staff change."""
    return {"request": {"kind": "edit_person", "person_id": str(ids["users"]["ben"]), "fields": fields}}


def reviewed(admin, request):
    """Return the exact confirmed request plus the server review evidence."""
    response = admin.post("/admin/changes/preview", json=request)
    assert response.status_code == 200, response.text
    plan = response.json()
    return {
        **request,
        "digest": plan["digest"],
        "revisions": plan["revisions"],
        "reason": "Annual staff review",
    }


def test_preview_and_apply_change_only_selected_staff_fields(as_user, ids, db_factory):
    admin = as_user("admin")
    request = edit(
        ids, display_name="  Ben O. Okafor  ", designation="Research Officer E", contact_phone="214"
    )
    confirmation = reviewed(admin, request)
    with db_factory() as db:
        person = db.get(User, ids["users"]["ben"])
        before = (
            person.display_name,
            person.revision,
            person.status,
            person.is_active,
            person.home_workspace_id,
        )
        assert before[0] == "Ben Okafor"
        assert db.scalar(select(func.count()).where(AuditEvent.action == "people.change")) == 0
    response = admin.post("/admin/changes/apply", json=confirmation)
    assert response.status_code == 200, response.text
    assert response.json()["revision"] == before[1] + 1
    profile = admin.get(f"/admin/people/{ids['users']['ben']}").json()
    assert profile["display_name"] == "Ben O. Okafor"
    assert profile["designation"] == "Research Officer E"
    assert profile["contact_phone"] == "214"
    with db_factory() as db:
        person = db.get(User, ids["users"]["ben"])
        assert (person.status, person.is_active, person.home_workspace_id) == before[2:]
        records = db.scalars(select(AuditEvent).where(AuditEvent.action.like("people.change%"))).all()
        assert len(records) == 2
        assert all(record.reason == "Annual staff review" for record in records)
        assert all(str(record.actor_id) == ids["users"]["admin"] for record in records)
        step = next(record for record in records if record.action == "people.change_step")
        assert step.detail["before"]["display_name"] == "Ben Okafor"
        assert step.detail["after"]["display_name"] == "Ben O. Okafor"
        assert step.detail["plan_digest"] == confirmation["digest"]
    assert admin.post("/admin/changes/apply", json=confirmation).status_code == 409


def test_stale_review_or_revision_writes_nothing(as_user, ids, db_factory):
    admin = as_user("admin")
    confirmation = reviewed(admin, edit(ids, designation="Research Officer E"))
    with db_factory() as db:
        person = db.get(User, ids["users"]["ben"])
        person.revision += 1
        db.commit()
    response = admin.post("/admin/changes/apply", json=confirmation)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "plan_stale"
    with db_factory() as db:
        assert db.get(User, ids["users"]["ben"]).designation is None
        assert db.scalar(select(AuditEvent.id).where(AuditEvent.action == "people.change")) is None


def test_confirmed_digest_cannot_authorize_different_fields_or_revisions(as_user, ids):
    admin = as_user("admin")
    confirmation = reviewed(admin, edit(ids, designation="Research Officer E"))
    changed = {**confirmation, **edit(ids, display_name="Different request")}
    assert admin.post("/admin/changes/apply", json=changed).status_code == 409
    confirmation["revisions"] = {}
    assert admin.post("/admin/changes/apply", json=confirmation).status_code == 409


def test_duplicate_employee_and_unchanged_records_are_blocked(as_user, ids, db_factory):
    admin = as_user("admin")
    with db_factory() as db:
        db.get(User, ids["users"]["chen"]).employee_no = "NW-200"
        db.commit()
    for request, code in [
        (edit(ids, employee_no="NW-200"), "duplicate_employee"),
        (edit(ids, display_name="Ben Okafor"), "no_changes"),
    ]:
        confirmation = reviewed(admin, request)
        plan = admin.post("/admin/changes/preview", json=request).json()
        assert plan["blockers"][0]["code"] == code
        response = admin.post("/admin/changes/apply", json=confirmation)
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "plan_blocked"


def test_last_audit_step_failure_rolls_back_entire_edit(as_user, ids, db_factory):
    admin = as_user("admin")
    confirmation = reviewed(admin, edit(ids, display_name="Ben O. Okafor"))
    with db_factory() as db:
        revision = db.get(User, ids["users"]["ben"]).revision
    with (
        patch.object(audit, "record_step", side_effect=RuntimeError("Synthetic final-step failure")),
        pytest.raises(RuntimeError, match="Synthetic final-step failure"),
    ):
        admin.post("/admin/changes/apply", json=confirmation)
    with db_factory() as db:
        person = db.get(User, ids["users"]["ben"])
        assert person.display_name == "Ben Okafor"
        assert person.revision == revision
        assert db.scalar(select(AuditEvent.id).where(AuditEvent.action == "people.change")) is None


def test_two_concurrent_confirmations_apply_once(as_user, ids, db_factory):
    first = as_user("admin")
    second = as_user("admin")
    confirmation = reviewed(first, edit(ids, designation="Research Officer E"))
    barrier = Barrier(2)

    def apply(client):
        barrier.wait(timeout=5)
        return client.post("/admin/changes/apply", json=confirmation).status_code

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(apply, [first, second]))
    assert sorted(results) == [200, 409]
    with db_factory() as db:
        assert db.scalar(select(func.count()).where(AuditEvent.action == "people.change")) == 1


@pytest.mark.parametrize("username", ["asha", "ben", "chen", "dana", "eli"])
def test_members_cannot_preview_or_apply(username, as_user, ids):
    member = as_user(username)
    request = edit(ids, designation="Research Officer E")
    assert member.post("/admin/changes/preview", json=request).status_code == 403
    assert member.post("/admin/changes/apply", json=request).status_code == 403


def test_reader_signed_out_disabled_and_panels_are_denied(as_user, ids, make_client):
    admin = as_user("admin")
    assert grant(admin, ids["users"]["ben"]).status_code == 201
    assert as_user("ben").post("/admin/changes/preview", json=edit(ids, designation="E")).status_code == 403
    signed_out = make_client()
    assert signed_out.post("/admin/changes/preview", json=edit(ids, designation="E")).status_code == 401
    assert signed_out.login("fay").status_code == 401
    panel = pair(as_user, make_client, ids)
    assert panel.post("/admin/changes/preview", json=edit(ids, designation="E")).status_code == 401
    assert (
        admin.post("/admin/changes/preview", json=edit(ids, designation="E"), headers=PANEL).status_code
        == 401
    )


@pytest.mark.parametrize(
    "fields",
    [
        {},
        {"display_name": " "},
        {"display_name": None},
        {"employee_no": "x" * 65},
        {"contact_email": "x" * 255},
        {"contact_phone": "x" * 65},
        {"designation": "x" * 121},
        {"designation": True},
        {"is_admin": True},
        {"username": "newname"},
        {"designation": "bad\x00text"},
    ],
)
def test_staff_field_bounds_and_whitelist(as_user, ids, fields):
    assert as_user("admin").post("/admin/changes/preview", json=edit(ids, **fields)).status_code == 422


def test_private_content_is_absent_and_optional_fields_can_be_cleared(as_user, ids, db_factory):
    marker = "Recognisable private project material"
    assert as_user("ben").post("/notes", json={"title": marker, "body": marker}).status_code == 201
    with db_factory() as db:
        db.get(User, ids["users"]["ben"]).contact_email = "ben@research.example"
        db.commit()
    admin = as_user("admin")
    request = edit(ids, contact_email="  ")
    plan = admin.post("/admin/changes/preview", json=request)
    assert marker not in plan.text
    assert "password_hash" not in plan.text
    confirmation = reviewed(admin, request)
    assert admin.post("/admin/changes/apply", json=confirmation).status_code == 200
    with db_factory() as db:
        assert db.get(User, ids["users"]["ben"]).contact_email is None


def test_authority_loss_before_lock_blocks_write(as_user, ids, db_factory):
    admin = as_user("admin")
    confirmation = reviewed(admin, edit(ids, designation="Research Officer E"))
    original = service.authorize

    def revoke_before_lock(db, actor, settings):
        with db_factory() as writer:
            writer.get(User, ids["users"]["admin"]).is_admin = False
            writer.commit()
        return original(db, actor, settings)

    with patch.object(service, "authorize", side_effect=revoke_before_lock):
        assert admin.post("/admin/changes/apply", json=confirmation).status_code == 403
    with db_factory() as db:
        assert db.get(User, ids["users"]["ben"]).designation is None


def test_database_failure_is_sanitized(as_user, ids):
    with patch.object(service, "preview", side_effect=OperationalError("private database detail", {}, None)):
        response = as_user("admin").post("/admin/changes/preview", json=edit(ids, designation="E"))
    assert response.status_code == 503
    assert "private database detail" not in response.text


def test_receipt_is_withheld_if_authority_disappears_after_commit(as_user, ids, db_factory, app):
    admin = as_user("admin")
    confirmation = reviewed(admin, edit(ids, designation="Research Officer E"))

    def demote_after_commit(person_id):
        with db_factory() as writer:
            person = writer.get(User, ids["users"]["ben"])
            assert str(person.id) == str(person_id)
            assert person.designation == "Research Officer E"
            writer.get(User, ids["users"]["admin"]).is_admin = False
            writer.commit()

    with patch.object(app.state.hub, "revalidate_user", side_effect=demote_after_commit):
        response = admin.post("/admin/changes/apply", json=confirmation)
    assert response.status_code == 403
    assert "Research Officer E" not in response.text
    with db_factory() as db:
        assert db.get(User, ids["users"]["ben"]).designation == "Research Officer E"
        assert db.scalar(select(func.count()).where(AuditEvent.action == "people.change")) == 1


def test_preview_never_writes_staff_or_audit_even_with_multiple_reads(as_user, ids, db_factory):
    admin = as_user("admin")
    request = edit(ids, designation="Research Officer E")
    before = admin.get(f"/admin/people/{ids['users']['ben']}").json()
    first = admin.post("/admin/changes/preview", json=request).json()
    second = admin.post("/admin/changes/preview", json=request).json()
    assert first == second
    assert admin.get(f"/admin/people/{ids['users']['ben']}").json() == before
    with db_factory() as db:
        assert db.scalar(select(AuditEvent.id).where(AuditEvent.action.like("people.change%"))) is None


def test_short_authority_timeout_does_not_cover_the_change_writes(as_user, ids):
    admin = as_user("admin")
    confirmation = reviewed(admin, edit(ids, designation="Research Officer E"))
    original = edit_person.apply
    seen = []

    def observe(db, *args):
        seen.append(db.scalar(text("show statement_timeout")))
        return original(db, *args)

    with patch.object(edit_person, "apply", side_effect=observe):
        assert admin.post("/admin/changes/apply", json=confirmation).status_code == 200
    assert seen and seen[0] != "2s"
