"""Reviewed onboarding: invited account, home membership, one-time code, guards and isolation."""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import patch

import pytest
from sqlalchemy import func, select

from labadda import audit
from labadda.models import AuditEvent, CredentialToken, Membership, User, Workspace
from tests.test_changes_edit import reviewed
from tests.test_panel import pair


def add(ids, username="gita", display_name="Gita Sen", unit="section_b", role="member", **extra):
    """Build a fictional onboarding request for the Catalysis Section by default."""
    return {
        "request": {
            "kind": "add_person",
            "username": username,
            "display_name": display_name,
            "home_unit_id": ids["workspaces"][unit],
            "role": role,
            **extra,
        }
    }


def preview(admin, request):
    response = admin.post("/admin/changes/preview", json=request)
    assert response.status_code == 200, response.text
    return response.json()


def people_count(db_factory) -> int:
    with db_factory() as db:
        return db.scalar(select(func.count()).select_from(User))


def test_add_creates_invited_person_with_home_membership_and_one_time_code(
    as_user, ids, db_factory, make_client
):
    admin = as_user("admin")
    request = add(
        ids,
        username="  Gita.Sen ",
        display_name=" Gita Sen ",
        role="steward",
        fields={"designation": "Scientific Officer C", "employee_no": "NW-310"},
        joined_on="2026-11-16",
    )
    plan = preview(admin, request)
    assert [step["summary"] for step in plan["steps"]] == [
        "Create an invited account for Gita Sen (gita.sen)",
        "Make Catalysis Section the home unit of Gita Sen, as steward",
        "Issue a one-time activation code",
    ]
    assert plan["blockers"] == [] and plan["affected_people"] == 1
    assert people_count(db_factory) == 7
    response = admin.post("/admin/changes/apply", json=reviewed(admin, request))
    assert response.status_code == 200, response.text
    receipt = response.json()
    assert receipt["kind"] == "add_person" and receipt["revision"] == 1
    code = receipt["activation"]["code"]
    assert len(code) >= 10 and receipt["activation"]["expires_at"]
    person_id = receipt["person_id"]
    profile = admin.get(f"/admin/people/{person_id}").json()
    assert profile["username"] == "gita.sen"
    assert profile["status"] == "invited"
    assert profile["home_unit"]["id"] == ids["workspaces"]["section_b"]
    assert profile["joined_on"] == "2026-11-16"
    assert profile["designation"] == "Scientific Officer C"
    with db_factory() as db:
        person = db.get(User, person_id)
        assert person.is_admin is False and person.must_set_password is True
        role = db.scalar(select(Membership.role).where(Membership.user_id == person.id))
        assert role == "steward"
        tokens = db.scalars(select(CredentialToken).where(CredentialToken.user_id == person.id)).all()
        assert len(tokens) == 1 and code not in tokens[0].token_hash
        events = db.scalars(select(AuditEvent).where(AuditEvent.action.like("people.change%"))).all()
        assert sorted(event.action for event in events) == ["people.change"] + ["people.change_step"] * 3
        assert {event.target_id for event in events if event.scope_type == "identity"} == {person_id}
        assert all(code not in str(event.detail) for event in events)
    newcomer = make_client()
    assert newcomer.login("gita.sen", "a-long-password").status_code == 401
    activate = newcomer.client.post(
        newcomer.url("/auth/activate"), json={"token": code, "password": "a-long-password"}
    )
    assert activate.status_code == 200
    assert make_client().login("gita.sen", "a-long-password").status_code == 200
    replay = admin.post("/admin/changes/apply", json=reviewed(admin, request) | {"digest": plan["digest"]})
    assert replay.status_code == 409


@pytest.mark.parametrize(
    ("request_overrides", "code"),
    [
        ({"username": "ben", "display_name": "Bilal Shah"}, "username_taken"),
        ({"fields": {"employee_no": "NW-200"}}, "duplicate_employee"),
        ({"unit": "project"}, "unit_unavailable"),
        ({"unit": "reading_club"}, "unit_unavailable"),
    ],
)
def test_blocked_onboarding_cannot_be_applied(request_overrides, code, as_user, ids, db_factory):
    with db_factory() as db:
        db.get(User, ids["users"]["chen"]).employee_no = "NW-200"
        db.commit()
    admin = as_user("admin")
    request = add(ids, **request_overrides)
    assert code in [blocker["code"] for blocker in preview(admin, request)["blockers"]]
    response = admin.post("/admin/changes/apply", json=reviewed(admin, request))
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "plan_blocked"
    assert people_count(db_factory) == 7


def test_archived_and_missing_home_units(as_user, ids, db_factory):
    admin = as_user("admin")
    with db_factory() as db:
        db.get(Workspace, ids["workspaces"]["section_b"]).archived = True
        db.commit()
    assert preview(admin, add(ids))["blockers"][0]["code"] == "unit_unavailable"
    missing = add(ids)
    missing["request"]["home_unit_id"] = ids["users"]["ben"]
    assert admin.post("/admin/changes/preview", json=missing).status_code == 404


@pytest.mark.parametrize("display_name", ["Ben Okafor", "Okafor, Ben", "Ben Okafr", "BEN OKAFOR"])
def test_very_similar_names_warn_without_blocking(display_name, as_user, ids):
    plan = preview(as_user("admin"), add(ids, username="bokafor", display_name=display_name))
    assert plan["blockers"] == []
    warning = plan["warnings"][0]
    assert warning["code"] == "similar_name"
    assert warning["target_id"] == ids["users"]["ben"]
    assert "Ben Okafor (ben)" in warning["message"]


def test_distinct_names_do_not_warn(as_user, ids):
    assert preview(as_user("admin"), add(ids))["warnings"] == []


@pytest.mark.parametrize(
    "change",
    [
        {"username": "x"},
        {"username": "Bad Name"},
        {"username": "ok\x00name"},
        {"display_name": "  "},
        {"display_name": "x" * 121},
        {"role": "owner"},
        {"is_admin": True},
        {"fields": {"designation": "x" * 121}},
        {"fields": {"status": "active"}},
        {"joined_on": "16/11/2026"},
    ],
)
def test_onboarding_bounds(change, as_user, ids):
    request = add(ids)
    request["request"].update(change)
    assert as_user("admin").post("/admin/changes/preview", json=request).status_code == 422


def test_concurrent_confirmations_create_one_person(as_user, ids, db_factory):
    first, second = as_user("admin"), as_user("admin")
    confirmation = reviewed(first, add(ids))
    barrier = Barrier(2)

    def confirm(client):
        barrier.wait(timeout=5)
        return client.post("/admin/changes/apply", json=confirmation).status_code

    with ThreadPoolExecutor(max_workers=2) as executor:
        assert sorted(executor.map(confirm, [first, second])) == [200, 409]
    assert people_count(db_factory) == 8


def test_failure_in_the_last_audit_step_writes_nothing(as_user, ids, db_factory):
    admin = as_user("admin")
    confirmation = reviewed(admin, add(ids))
    original = audit.record_step

    def fail_last(*args, **kwargs):
        if kwargs["index"] == 2:
            raise RuntimeError("Synthetic final-step failure")
        return original(*args, **kwargs)

    with patch.object(audit, "record_step", side_effect=fail_last), pytest.raises(RuntimeError):
        admin.post("/admin/changes/apply", json=confirmation)
    assert people_count(db_factory) == 7
    with db_factory() as db:
        assert db.scalar(select(func.count()).select_from(CredentialToken)) == 0
        recorded = db.scalars(select(AuditEvent.action).where(AuditEvent.action != "auth.login")).all()
        assert recorded == []
        assert db.scalar(select(func.count()).select_from(Membership)) == 9


@pytest.mark.parametrize("username", ["asha", "ben", "chen", "dana", "eli"])
def test_members_cannot_onboard(username, as_user, ids):
    member = as_user(username)
    assert member.post("/admin/changes/preview", json=add(ids)).status_code == 403


def test_signed_out_and_panels_cannot_onboard(as_user, ids, make_client):
    assert make_client().post("/admin/changes/preview", json=add(ids)).status_code == 401
    panel = pair(as_user, make_client, ids)
    assert panel.post("/admin/changes/preview", json=add(ids)).status_code == 401


def test_onboarding_responses_carry_no_private_content(as_user, ids):
    marker = "Recognisable onboarding secret material"
    assert as_user("ben").post("/notes", json={"title": marker, "body": marker}).status_code == 201
    unit = ids["workspaces"]["section_a"]
    assert as_user("ben").post(f"/workspaces/{unit}/posts", json={"body": marker}).status_code == 201
    admin = as_user("admin")
    request = add(ids, display_name="Ben Okafor", username="bokafor")
    plan = admin.post("/admin/changes/preview", json=request)
    receipt = admin.post("/admin/changes/apply", json=reviewed(admin, request))
    for response in (plan, receipt):
        assert response.status_code == 200
        assert marker not in response.text
        assert "password_hash" not in response.text and "token_hash" not in response.text
