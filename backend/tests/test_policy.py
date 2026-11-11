"""T01: tree and grants across levels, siblings, project, archive, steward, admin, disabled."""

import pytest

from labadda import policy
from labadda.models import User


def readable_names(as_user, username):
    r = as_user(username).get("/workspaces")
    assert r.status_code == 200
    return {w["name"]: w for w in r.json()["workspaces"]}


def test_upward_visibility_for_section_member(as_user):
    names = readable_names(as_user, "ben")
    assert set(names) == {
        "Thin Films Section",
        "Surface Science Division",
        "Materials Group",
        "Northwind Research",
        "Microscopy Reading Club",
    }
    assert names["Thin Films Section"]["role"] == "member"
    assert names["Surface Science Division"]["inherited"] is True
    assert names["Surface Science Division"]["can_moderate"] is False


def test_division_steward_does_not_see_sections(as_user):
    names = readable_names(as_user, "dana")
    assert "Thin Films Section" not in names and "Catalysis Section" not in names
    assert names["Surface Science Division"]["can_moderate"] is True
    assert names["Materials Group"]["can_moderate"] is False  # steward authority stays direct


def test_sibling_isolation(as_user, ids):
    chen = as_user("chen")
    assert chen.get(f"/workspaces/{ids['workspaces']['section_a']}").status_code == 404
    assert chen.get(f"/workspaces/{ids['workspaces']['section_a']}/posts").status_code == 404
    # Unknown ID looks identical to an out-of-scope one.
    unknown = chen.get("/workspaces/00000000-0000-0000-0000-000000000000/posts")
    hidden = chen.get(f"/workspaces/{ids['workspaces']['section_a']}/posts")
    assert unknown.status_code == hidden.status_code == 404
    assert unknown.json() == hidden.json()


def test_project_is_independent(as_user, ids):
    names = readable_names(as_user, "eli")
    assert set(names) == {"Project Aurora"}
    assert as_user("ben").get(f"/workspaces/{ids['workspaces']['project']}").status_code == 404


def test_admin_without_grant_has_no_content(as_user, ids):
    admin = as_user("admin")
    assert readable_names(as_user, "admin") == {}
    for key in ("root", "division", "section_a", "project", "reading_club"):
        assert admin.get(f"/workspaces/{ids['workspaces'][key]}/posts").status_code == 404
    assert admin.get("/admin/users").status_code == 200


def test_disabled_account_cannot_sign_in(make_client):
    r = make_client().login("fay")
    assert r.status_code == 401


def test_non_admin_cannot_administer(as_user):
    assert as_user("dana").get("/admin/users").status_code == 403


def test_policy_resolve_inactive_user_gets_nothing(db_factory, ids):
    with db_factory() as db:
        fay = db.get(User, __import__("uuid").UUID(ids["users"]["fay"]))
        assert policy.readable_workspace_ids(db, fay) == {}


def test_eligible_readers_include_descendants(db_factory, ids):
    import uuid

    from labadda.models import Workspace

    with db_factory() as db:
        division = db.get(Workspace, uuid.UUID(ids["workspaces"]["division"]))
        readers = policy.eligible_reader_ids(db, division)
        expected = {uuid.UUID(ids["users"][u]) for u in ("asha", "ben", "chen", "dana")}
        assert readers == expected  # fay is disabled; eli is project-only


@pytest.mark.parametrize("key,expected", [("section_a", 200), ("division", 200), ("section_b", 404)])
def test_member_matrix(as_user, ids, key, expected):
    assert as_user("asha").get(f"/workspaces/{ids['workspaces'][key]}/posts").status_code == expected


def test_archive_keeps_reads_blocks_writes(as_user, ids):
    admin = as_user("admin")
    ws = ids["workspaces"]["section_a"]
    assert admin.patch(f"/admin/workspaces/{ws}", json={"archived": True}).status_code == 200
    ben = as_user("ben")
    assert ben.get(f"/workspaces/{ws}/posts").status_code == 200
    r = ben.post(f"/workspaces/{ws}/posts", json={"body": "hello"})
    assert r.status_code == 403 and r.json()["error"]["code"] == "workspace_archived"


def test_transfer_moves_access(as_user, ids):
    admin = as_user("admin")
    ben_id = ids["users"]["ben"]
    a, b = ids["workspaces"]["section_a"], ids["workspaces"]["section_b"]
    assert admin.delete(f"/admin/workspaces/{a}/memberships/{ben_id}").status_code == 200
    assert admin.put(f"/admin/workspaces/{b}/memberships", json={"user_id": ben_id}).status_code == 200
    ben = as_user("ben")
    assert ben.get(f"/workspaces/{a}/posts").status_code == 404
    assert ben.get(f"/workspaces/{b}/posts").status_code == 200
    home = ben.get("/workspaces").json()["home_workspace_id"]
    assert home in (b, ids["workspaces"]["reading_club"])  # lost home falls back to a direct grant


def test_tree_cycle_rejected_and_grants_intact(as_user, ids):
    admin = as_user("admin")
    root, sec = ids["workspaces"]["root"], ids["workspaces"]["section_a"]
    r = admin.patch(f"/admin/workspaces/{root}", json={"move": True, "parent_id": sec})
    assert r.status_code == 422 and r.json()["error"]["code"] == "cycle"
    second_root = admin.post("/admin/workspaces", json={"name": "Another Root", "kind": "org"})
    assert second_root.status_code == 422
    assert as_user("ben").get(f"/workspaces/{sec}/posts").status_code == 200


def test_db_trigger_rejects_cycle(db_factory, ids):
    import uuid

    import sqlalchemy

    from labadda.models import Workspace

    with db_factory() as db:
        root = db.get(Workspace, uuid.UUID(ids["workspaces"]["root"]))
        root.parent_id = uuid.UUID(ids["workspaces"]["section_b"])
        with pytest.raises(sqlalchemy.exc.DBAPIError):
            db.commit()


def test_admin_can_move_unit(as_user, ids):
    admin = as_user("admin")
    sec_b, group = ids["workspaces"]["section_b"], ids["workspaces"]["group"]
    assert (
        admin.patch(f"/admin/workspaces/{sec_b}", json={"move": True, "parent_id": group}).status_code == 200
    )
    names = readable_names(as_user, "chen")
    assert "Surface Science Division" not in names and "Materials Group" in names
