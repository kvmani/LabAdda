"""S2.1 collaborative groups: user-created, flat, direct grants only."""


def make_group(api, ids, members=("chen",), name="Spectroscopy Journal Club"):
    r = api.post("/groups", json={"name": name, "description": "Weekly paper reading",
                                  "member_ids": [ids["users"][m] for m in members]})
    assert r.status_code == 201, r.text
    return r.json()


def test_any_user_creates_group_with_chosen_colleagues(as_user, ids):
    asha = as_user("asha")
    group = make_group(asha, ids, members=("chen", "eli"))
    assert group["kind"] == "group" and group["role"] == "steward" and group["parent_id"] is None
    members = asha.get(f"/workspaces/{group['id']}/members").json()["members"]
    assert {m["username"]: m["role"] for m in members} == {"asha": "steward", "chen": "member", "eli": "member"}
    # Colleagues from a sibling section and a project can now collaborate here.
    for user in ("chen", "eli"):
        names = {w["name"] for w in as_user(user).get("/workspaces").json()["workspaces"]}
        assert "Spectroscopy Journal Club" in names


def test_group_has_all_workspace_features(as_user, ids):
    asha, chen = as_user("asha"), as_user("chen")
    g = make_group(asha, ids)["id"]
    post = chen.post(f"/workspaces/{g}/posts", json={"body": "Paper for Friday",
                                                     "due_at": "2030-01-10T09:00:00+00:00"})
    assert post.status_code == 201
    assert asha.post(f"/posts/{post.json()['id']}/replies", json={"body": "Thanks"}).status_code == 201
    assert asha.post(f"/posts/{post.json()['id']}/pin", json={"pinned": True}).status_code == 200
    assert chen.post(f"/workspaces/{g}/chat", json={"body": "hello group", "client_id": "chat-0001"}).status_code == 201
    board = chen.get(f"/workspaces/{g}/board").json()
    op = chen.post(f"/workspaces/{g}/board/ops", json={
        "op_id": "op-000001", "epoch": board["epoch"], "type": "add", "object_id": "obj-1",
        "payload": {"kind": "sticky", "data": {"x": 10, "y": 10, "text": "Agenda", "color": "#fff59d"}}})
    assert op.status_code == 200
    assert asha.get(f"/workspaces/{g}/upcoming").json()["items"][0]["title"] == "Paper for Friday"
    assert asha.get(f"/workspaces/{g}/search", params={"q": "hello"}).json()["counts"]["chat"] == 1
    official = asha.post(f"/workspaces/{g}/posts", json={"body": "Official: venue changed", "kind": "official"})
    assert official.status_code == 201
    assert chen.post(f"/workspaces/{g}/posts", json={"body": "x", "kind": "official"}).status_code == 403


def test_no_hierarchy_inheritance(as_user, ids):
    g = make_group(as_user("asha"), ids)["id"]
    # Division steward, unrelated members and admin cannot see the group.
    for user in ("dana", "ben", "admin", "eli"):
        assert as_user(user).get(f"/workspaces/{g}/posts").status_code == 404
    # A group cannot be given a parent.
    r = as_user("admin").patch(f"/admin/workspaces/{g}", json={"move": True,
                                                              "parent_id": ids["workspaces"]["division"]})
    assert r.status_code == 422


def test_group_content_not_visible_in_parent_units(as_user, ids):
    asha = as_user("asha")
    g = make_group(asha, ids)["id"]
    asha.post(f"/workspaces/{g}/posts", json={"body": "group-only secret plan"})
    div = ids["workspaces"]["division"]
    r = as_user("dana").get(f"/workspaces/{div}/search", params={"q": "secret"})
    assert r.json()["counts"] == {"posts": 0, "chat": 0}


def test_only_stewards_manage_members(as_user, ids):
    asha, chen = as_user("asha"), as_user("chen")
    g = make_group(asha, ids)["id"]
    r = chen.post(f"/groups/{g}/members", json={"user_ids": [ids["users"]["ben"]]})
    assert r.status_code == 403
    assert chen.patch(f"/groups/{g}", json={"name": "Renamed"}).status_code == 403
    r = asha.post(f"/groups/{g}/members", json={"user_ids": [ids["users"]["ben"]]})
    assert r.status_code == 200 and r.json()["added"][0]["username"] == "ben"
    assert as_user("ben").get(f"/workspaces/{g}/posts").status_code == 200
    assert asha.delete(f"/groups/{g}/members/{ids['users']['ben']}").status_code == 200
    assert as_user("ben").get(f"/workspaces/{g}/posts").status_code == 404


def test_members_can_leave_and_last_steward_is_protected(as_user, ids):
    asha, chen = as_user("asha"), as_user("chen")
    g = make_group(asha, ids)["id"]
    r = asha.delete(f"/groups/{g}/members/{ids['users']['asha']}")
    assert r.status_code == 409 and r.json()["error"]["code"] == "last_steward"
    r = asha.patch(f"/groups/{g}/members/{ids['users']['asha']}", json={"role": "member"})
    assert r.status_code == 409
    assert asha.patch(f"/groups/{g}/members/{ids['users']['chen']}", json={"role": "steward"}).status_code == 200
    assert asha.delete(f"/groups/{g}/members/{ids['users']['asha']}").status_code == 200
    assert asha.get(f"/workspaces/{g}").status_code == 404
    assert chen.get(f"/workspaces/{g}").json()["can_moderate"] is True


def test_inactive_or_unknown_invitees_rejected(as_user, ids):
    r = as_user("asha").post("/groups", json={"name": "X", "member_ids": [ids["users"]["fay"]]})
    assert r.status_code == 422 and r.json()["error"]["code"] == "unknown_member"


def test_archive_freezes_group(as_user, ids):
    asha, chen = as_user("asha"), as_user("chen")
    g = make_group(asha, ids)["id"]
    assert asha.patch(f"/groups/{g}", json={"archived": True}).status_code == 200
    assert chen.get(f"/workspaces/{g}/posts").status_code == 200
    assert chen.post(f"/workspaces/{g}/posts", json={"body": "late"}).status_code == 403
    assert asha.post(f"/groups/{g}/members", json={"user_ids": [ids["users"]["ben"]]}).status_code == 403
    assert asha.patch(f"/groups/{g}", json={"archived": False}).status_code == 200


def test_group_endpoints_do_not_apply_to_org_units(as_user, ids):
    asha = as_user("asha")
    sec = ids["workspaces"]["section_a"]
    assert asha.post(f"/groups/{sec}/members", json={"user_ids": [ids["users"]["chen"]]}).status_code == 404
    assert as_user("chen").post(f"/groups/{sec}/members", json={"user_ids": [ids["users"]["chen"]]}).status_code == 404


def test_directory_returns_names_only(as_user):
    r = as_user("asha").get("/directory", params={"q": "ch"})
    assert r.status_code == 200
    users = r.json()["users"]
    assert [u["username"] for u in users] == ["chen"]
    assert set(users[0]) == {"id", "username", "display_name", "is_active"}
    assert all(u["username"] != "fay" for u in as_user("asha").get("/directory").json()["users"])


def test_group_limit(as_user, ids, app):
    from dataclasses import replace
    app.state.settings = replace(app.state.settings, max_groups_per_user=1)
    asha = as_user("asha")
    make_group(asha, ids, name="One")
    r = asha.post("/groups", json={"name": "Two"})
    assert r.status_code == 409 and r.json()["error"]["code"] == "group_limit"


def test_group_membership_audited(as_user, ids):
    make_group(as_user("asha"), ids)
    events = as_user("admin").get("/admin/audit").json()["events"]
    actions = {e["action"] for e in events}
    assert {"group.create", "membership.set"} <= actions


def test_users_cannot_create_org_units_via_groups(as_user):
    r = as_user("asha").post("/admin/workspaces", json={"name": "Rogue", "kind": "org"})
    assert r.status_code == 403
