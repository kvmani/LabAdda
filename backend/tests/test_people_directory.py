"""P1 directory filters, stable bounded pages, privacy and current-authority delivery."""

import time
import uuid
from datetime import date
from unittest.mock import patch

import pytest
from sqlalchemy.exc import OperationalError

from labadda import people_directory
from labadda.models import User
from tests.test_capabilities import grant
from tests.test_panel import PANEL, pair


def add_people(db_factory, ids, count=12):
    """Create fictional staff efficiently, with duplicate names and optional identifiers."""
    with db_factory() as db:
        password_hash = db.get(User, ids["users"]["bharat"]).password_hash
        staff = [
            User(
                username=f"employee{index:03}",
                display_name=f"Directory Person {index // 2:03}",
                password_hash=password_hash,
                must_set_password=False,
                status="active",
                employee_no=f"NM-{index:03}" if index % 2 == 0 else None,
                home_workspace_id=ids["workspaces"]["section_a"],
            )
            for index in range(count)
        ]
        db.add_all(staff)
        db.commit()
        return [person.id for person in staff]


def test_directory_search_filters_and_home_subunits(as_user, ids, db_factory):
    add_people(db_factory, ids)
    admin = as_user("admin")
    assert len(admin.get("/admin/people?q=nm-000").json()["people"]) == 1
    assert len(admin.get("/admin/people?q=EMPLOYEE00").json()["people"]) == 10
    assert admin.get("/admin/people?q=%25").json()["people"] == []
    assert admin.get("/admin/people?status=left").json()["people"][0]["username"] == "farhan"
    branch = ids["workspaces"]["division"]
    rows = admin.get(f"/admin/people?unit_id={branch}").json()["people"]
    assert any(person["username"] == "bharat" for person in rows)
    direct = admin.get(f"/admin/people?unit_id={branch}&include_children=false").json()["people"]
    assert [person["username"] for person in direct] == ["deepa"]
    assert all(person["is_admin"] for person in admin.get("/admin/people?role=admin").json()["people"])
    section = ids["workspaces"]["section_a"]
    stewards = admin.get(f"/admin/people?unit_id={section}&role=steward").json()["people"]
    assert [person["username"] for person in stewards] == ["asha"]
    assert admin.get(f"/admin/people?unit_id={ids['workspaces']['project']}").status_code == 404
    assert admin.get(f"/admin/people?unit_id={uuid.uuid4()}").status_code == 404


@pytest.mark.parametrize("sort", ["name", "username", "employee_no", "status", "last_seen_on"])
@pytest.mark.parametrize("descending", [False, True])
def test_paging_keeps_ties_and_nulls_without_duplicates(as_user, ids, db_factory, sort, descending):
    wanted = add_people(db_factory, ids)
    with db_factory() as db:
        db.get(User, wanted[0]).last_seen_on = date(2026, 11, 10)
        db.commit()
    admin = as_user("admin")
    cursor = None
    found = []
    pages = 0
    while True:
        query = {"q": "Directory Person", "limit": 2, "sort": sort, "descending": str(descending).lower()}
        if cursor:
            query["cursor"] = cursor
        response = admin.get("/admin/people", params=query)
        assert response.status_code == 200, response.text
        page = response.json()
        found.extend(person["id"] for person in page["people"])
        pages += 1
        assert pages <= 6
        cursor = page["next_cursor"]
        if not cursor:
            break
    assert len(found) == len(set(found)) == len(wanted)
    assert set(found) == {str(identity) for identity in wanted}
    if sort == "last_seen_on":
        assert found[0] == str(wanted[0])


def test_cursor_binding_and_input_bounds(as_user, ids, db_factory):
    add_people(db_factory, ids)
    admin = as_user("admin")
    first = admin.get("/admin/people?limit=1").json()
    assert (
        admin.get("/admin/people", params={"cursor": first["next_cursor"], "q": "different"}).status_code
        == 422
    )
    for query in (
        "limit=0",
        "limit=101",
        "sort=invalid",
        "role=invalid",
        "status=invalid",
        "cursor=invalid",
        "q=" + "x" * 121,
    ):
        assert admin.get("/admin/people?" + query).status_code == 422


@pytest.mark.parametrize("name", ["asha", "bharat", "chitra", "deepa", "esha"])
def test_non_administrators_do_not_get_staff_directory(as_user, name):
    assert as_user(name).get("/admin/people").status_code == 403


def test_reader_panel_signed_out_and_disabled_are_denied(as_user, ids, make_client):
    assert grant(as_user("admin"), ids["users"]["bharat"]).status_code == 201
    assert as_user("bharat").get("/admin/people").status_code == 403
    assert make_client().get("/admin/people").status_code == 401
    client = make_client()
    assert client.login("farhan").status_code == 401
    assert client.get("/admin/people").status_code == 401
    assert pair(as_user, make_client, ids).get("/admin/people").status_code == 401
    assert as_user("admin").get("/admin/people", headers=PANEL).status_code == 401


def test_directory_never_contains_private_contacts_or_content(as_user, ids, db_factory):
    private = "Recognisable private staff test material"
    member = as_user("bharat")
    assert member.post("/notes", json={"title": private, "body": private}).status_code == 201
    with db_factory() as db:
        person = db.get(User, ids["users"]["bharat"])
        person.contact_email = "private-contact@research.example"
        db.commit()
    response = as_user("admin").get("/admin/people")
    assert response.status_code == 200
    assert private not in response.text
    assert "private-contact" not in response.text
    assert "password" not in response.text
    seen = next(person for person in response.json()["people"] if person["username"] == "bharat")[
        "last_seen_on"
    ]
    assert len(seen) == 10 and "T" not in seen


def test_500_people_query_stays_within_the_card_budget(as_user, ids, db_factory):
    add_people(db_factory, ids, count=500)
    admin = as_user("admin")
    started = time.perf_counter()
    response = admin.get("/admin/people?q=employee&limit=100")
    elapsed = time.perf_counter() - started
    assert response.status_code == 200
    assert len(response.json()["people"]) == 100
    assert elapsed < 0.2, f"500-person directory query took {elapsed * 1000:.1f}ms"


def test_authority_loss_during_read_discards_the_payload(as_user, ids, db_factory):
    admin = as_user("admin")
    original = people_directory.directory_page

    def revoke_after_read(*args, **kwargs):
        payload = original(*args, **kwargs)
        with db_factory() as db:
            db.get(User, ids["users"]["admin"]).is_admin = False
            db.commit()
        return payload

    with patch.object(people_directory, "directory_page", side_effect=revoke_after_read):
        response = admin.get("/admin/people")
    assert response.status_code == 403
    assert "username" not in response.text


def test_database_failure_is_unavailable_not_an_empty_directory(as_user):
    failure = OperationalError("private search term", {}, Exception("private diagnostic"))
    with patch.object(people_directory, "directory_page", side_effect=failure):
        response = as_user("admin").get("/admin/people")
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "people_unavailable"
    assert "private" not in response.text
