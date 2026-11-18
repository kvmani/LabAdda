"""Verified affiliation, identity collision and serialized decision regressions."""

import uuid
from concurrent.futures import ThreadPoolExecutor
from threading import Event

import pytest
from sqlalchemy import select

from labadda import joining
from labadda.models import JoinRequest, User, Workspace
from tests.test_panel import pair


def pending(db_factory, unit_id=None, **values):
    with db_factory() as db:
        request = JoinRequest(full_name="Anita Rao", username="anita.rao", unit_id=unit_id, **values)
        db.add(request)
        db.commit()
        return str(request.id)


@pytest.mark.parametrize("kind", ["group", "project"])
def test_public_affiliations_exclude_private_spaces(make_client, as_user, ids, db_factory, kind):
    with db_factory() as db:
        workspace = db.scalar(select(Workspace).where(Workspace.kind == kind))
        workspace_id, name = workspace.id, workspace.name
    anon = make_client()
    catalogue = anon.get("/join-requests/units")
    assert name not in catalogue.text
    assert all(row["kind"] == "org" for row in catalogue.json()["units"])
    assert (
        anon.post(
            "/join-requests",
            json={"full_name": "Anita Rao", "username": "anita.rao", "unit_id": str(workspace_id)},
        ).status_code
        == 422
    )
    request_id = pending(db_factory, workspace_id)
    result = as_user("admin").post(f"/admin/join-requests/{request_id}/approve")
    assert result.status_code == 422
    assert result.json()["error"]["code"] == "invalid_unit"


def test_archived_or_missing_affiliation_never_substitutes_root(as_user, ids, db_factory):
    unit = uuid.UUID(ids["workspaces"]["section_a"])
    request_id = pending(db_factory, unit)
    with db_factory() as db:
        db.get(Workspace, unit).archived = True
        db.commit()
    admin = as_user("admin")
    assert admin.post(f"/admin/join-requests/{request_id}/approve").status_code == 422
    with db_factory() as db:
        row = db.get(JoinRequest, uuid.UUID(request_id))
        row.unit_id = None
        db.commit()
    response = admin.post(f"/admin/join-requests/{request_id}/approve")
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "affiliation_required"
    with db_factory() as db:
        assert db.get(JoinRequest, uuid.UUID(request_id)).status == "pending"
        assert db.scalar(select(User.id).where(User.username == "anita.rao")) is None


@pytest.mark.parametrize("identity", ["username", "employee_no"])
def test_approval_rechecks_unchanged_identity(as_user, ids, db_factory, identity):
    request_id = pending(db_factory, uuid.UUID(ids["workspaces"]["section_a"]), employee_no="EMP-REVIEW")
    with db_factory() as db:
        person = User(
            username="anita.rao" if identity == "username" else "sunita.rao",
            display_name="Sunita Rao",
            employee_no="emp-review" if identity == "employee_no" else None,
        )
        db.add(person)
        db.commit()
    response = as_user("admin").post(f"/admin/join-requests/{request_id}/approve")
    assert response.status_code == 409
    assert response.json()["error"]["code"] == (
        "username_taken" if identity == "username" else "employee_no_taken"
    )


def test_approval_and_rejection_cannot_both_succeed(as_user, make_client, ids, db_factory, monkeypatch):
    request_id = pending(db_factory, uuid.UUID(ids["workspaces"]["section_a"]))
    approving, rejecting = make_client("admin"), make_client("admin")
    reached, release = Event(), Event()
    original = joining.check_identity

    def paused(*args):
        reached.set()
        assert release.wait(10)
        return original(*args)

    monkeypatch.setattr(joining, "check_identity", paused)
    with ThreadPoolExecutor(max_workers=2) as pool:
        approval = pool.submit(approving.post, f"/admin/join-requests/{request_id}/approve")
        assert reached.wait(10)
        rejection = pool.submit(
            rejecting.post, f"/admin/join-requests/{request_id}/reject", json={"reason": "Not verified"}
        )
        release.set()
        assert approval.result(timeout=10).status_code == 200
        assert rejection.result(timeout=10).status_code == 409
    with db_factory() as db:
        row = db.get(JoinRequest, uuid.UUID(request_id))
        assert row.status == "approved"
        person = db.get(User, row.created_user_id)
        assert person.status == "invited" and not person.is_admin and person.must_set_password
    assert as_user("admin").post(f"/admin/join-requests/{request_id}/approve").status_code == 409


def test_application_denials_and_bounded_pagination(as_user, make_client, ids, db_factory):
    request_id = pending(db_factory)
    paths = [
        "/admin/join-requests",
        f"/admin/join-requests/{request_id}/approve",
        f"/admin/join-requests/{request_id}/reject",
    ]
    for client, status in [
        (make_client(), 401),
        (as_user("bharat"), 403),
        (as_user("asha"), 403),
        (pair(as_user, make_client, ids), 401),
    ]:
        assert client.get(paths[0]).status_code == status
        for path in paths[1:]:
            assert client.post(path).status_code == status
    admin = as_user("admin")
    assert admin.get(paths[0], params={"status": "nonsense"}).status_code == 422
    assert admin.get(paths[0], params={"limit": 101}).status_code == 422
    assert admin.get(paths[0], params={"limit": 1}).json()["next_offset"] is None
