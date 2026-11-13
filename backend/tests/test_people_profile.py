"""P1 profiles, retained access and date-only history exclude all private content."""

import uuid

import pytest

from labadda import audit
from labadda.models import User
from tests.test_capabilities import grant
from tests.test_panel import PANEL, pair


def routes(identity):
    return (
        f"/admin/people/{identity}",
        f"/admin/people/{identity}/access",
        f"/admin/people/{identity}/timeline",
    )


def test_profile_and_upward_access_without_admin_or_home_bypass(as_user, ids, db_factory):
    admin = as_user("admin")
    with db_factory() as db:
        person = db.get(User, ids["users"]["bharat"])
        person.employee_no = "NM-100"
        person.contact_email = "bharat@research.example"
        db.commit()
    person = admin.get(routes(ids["users"]["bharat"])[0]).json()
    assert person["employee_no"] == "NM-100"
    assert person["contact_email"] == "bharat@research.example"
    assert person["joined_on"] is None
    assert person["home_unit"]["name"] == "Thin Films Section"
    assert "password_hash" not in person
    bharat = admin.get(routes(ids["users"]["bharat"])[1]).json()["memberships"]
    targets = {row["workspace"]["id"]: row for row in bharat}
    assert str(ids["workspaces"]["section_b"]) not in targets
    assert targets[str(ids["workspaces"]["division"])]["inherited"]
    assert targets[str(ids["workspaces"]["division"])]["role"] == "member"
    assert not targets[str(ids["workspaces"]["section_a"])]["inherited"]
    deepa = admin.get(routes(ids["users"]["deepa"])[1]).json()["memberships"]
    assert str(ids["workspaces"]["section_a"]) not in {row["workspace"]["id"] for row in deepa}
    assert admin.get(routes(ids["users"]["admin"])[1]).json()["memberships"] == []
    departed = admin.get(routes(ids["users"]["farhan"])[1]).json()["memberships"]
    assert departed and all(not row["sign_in_enabled"] for row in departed)


def test_access_pages_are_bounded_without_duplicates(as_user, ids):
    admin = as_user("admin")
    path = routes(ids["users"]["bharat"])[1]
    cursor = None
    found = []
    while True:
        page = admin.get(path, params={"limit": 1, **({"cursor": cursor} if cursor else {})}).json()
        found.extend(row["workspace"]["id"] for row in page["memberships"])
        cursor = page["next_cursor"]
        if not cursor:
            break
    assert len(found) == len(set(found))
    assert len(found) > 1
    assert admin.get(path + "?limit=0").status_code == 422


def test_history_is_plain_date_only_and_drops_unrecognised_detail(as_user, ids, db_factory):
    private = "Private note title chat message post body filename.pdf"
    with db_factory() as db:
        audit.record(
            db,
            actor=ids["users"]["admin"],
            action="identity.update",
            scope_type="identity",
            target_id=ids["users"]["bharat"],
            reason="Synthetic staff review",
            private_text=private,
        )
        audit.record(
            db,
            actor=None,
            action="unrecognised",
            scope_type="identity",
            target_id=ids["users"]["bharat"],
            reason=private,
            private_text=private,
        )
        db.commit()
    path = routes(ids["users"]["bharat"])[2]
    response = as_user("admin").get(path, params={"limit": 1})
    assert response.status_code == 200
    first = response.json()
    assert private not in response.text
    assert first["items"][0]["summary"] == "Staff-related activity recorded"
    assert first["items"][0]["reason"] is None
    assert len(first["items"][0]["occurred_on"]) == 10
    following = as_user("admin").get(path, params={"before": first["next_cursor"]}).json()
    assert following["items"][0]["summary"] == "Account updated"
    assert following["items"][0]["reason"] == "Synthetic staff review"


@pytest.mark.parametrize("name", ["asha", "bharat", "chitra", "deepa", "esha"])
def test_profile_routes_deny_non_administrators(as_user, ids, name):
    for path in (*routes(ids["users"]["bharat"]), "/admin/people/export.csv"):
        assert as_user(name).get(path).status_code == 403


def test_profile_routes_deny_reader_panel_disabled_and_signed_out(as_user, make_client, ids):
    admin = as_user("admin")
    assert grant(admin, ids["users"]["bharat"]).status_code == 201
    kiosk = pair(as_user, make_client, ids)
    inactive = make_client()
    assert inactive.login("farhan").status_code == 401
    for path in (*routes(ids["users"]["bharat"]), "/admin/people/export.csv"):
        assert as_user("bharat").get(path).status_code == 403
        assert kiosk.get(path).status_code == 401
        assert inactive.get(path).status_code == 401
        assert admin.get(path, headers=PANEL).status_code == 401
    for path in routes(uuid.uuid4()):
        assert admin.get(path).status_code == 404


def test_no_content_in_any_staff_response(as_user, ids):
    member = as_user("bharat")
    marker = "Recognisable private collaboration material"
    workspace = ids["workspaces"]["section_a"]
    assert member.post("/notes", json={"title": marker, "body": marker}).status_code == 201
    assert member.post(f"/workspaces/{workspace}/posts", json={"body": marker}).status_code == 201
    assert (
        member.post(
            f"/workspaces/{workspace}/chat", json={"body": marker, "client_id": str(uuid.uuid4())}
        ).status_code
        == 201
    )
    assert (
        member.post(
            "/uploads",
            files={"file": ("private-staff-marker.pdf", b"%PDF-1.4\nfixture\n%%EOF", "application/pdf")},
        ).status_code
        == 201
    )
    for path in ("/admin/people", *routes(ids["users"]["bharat"]), "/admin/people/export.csv"):
        response = as_user("admin").get(path)
        assert response.status_code == 200
        assert marker not in response.text
        assert "private-staff-marker.pdf" not in response.text
