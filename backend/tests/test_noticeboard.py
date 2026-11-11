"""T04, T05: posts, replies, pins, official notices, read-only, scoped search and IDs."""


def sec(ids, key="section_a"):
    return ids["workspaces"][key]


def test_create_reload_edit_delete(as_user, ids):
    ben = as_user("ben")
    r = ben.post(f"/workspaces/{sec(ids)}/posts", json={"body": "XRD schedule posted", "client_id": "p-1"})
    assert r.status_code == 201
    post = r.json()
    feed = ben.get(f"/workspaces/{sec(ids)}/posts").json()
    assert feed["posts"][0]["body"] == "XRD schedule posted"
    assert ben.patch(f"/posts/{post['id']}", json={"body": "XRD schedule updated"}).json()["edited_at"]
    assert as_user("asha").patch(f"/posts/{post['id']}", json={"body": "hijack"}).status_code == 403
    assert ben.delete(f"/posts/{post['id']}").status_code == 200
    assert ben.get(f"/workspaces/{sec(ids)}/posts").json()["posts"] == []


def test_idempotent_retry_and_changed_reuse(as_user, ids):
    ben = as_user("ben")
    a = ben.post(f"/workspaces/{sec(ids)}/posts", json={"body": "once", "client_id": "retry-1"})
    b = ben.post(f"/workspaces/{sec(ids)}/posts", json={"body": "once", "client_id": "retry-1"})
    assert a.json()["id"] == b.json()["id"]
    c = ben.post(f"/workspaces/{sec(ids)}/posts", json={"body": "different", "client_id": "retry-1"})
    assert c.status_code == 409
    assert len(ben.get(f"/workspaces/{sec(ids)}/posts").json()["posts"]) == 1


def test_replies_and_pagination(as_user, ids):
    ben = as_user("ben")
    for i in range(25):
        ben.post(f"/workspaces/{sec(ids)}/posts", json={"body": f"post {i}"})
    page1 = ben.get(f"/workspaces/{sec(ids)}/posts", params={"limit": 10}).json()
    page2 = ben.get(
        f"/workspaces/{sec(ids)}/posts", params={"limit": 10, "before": page1["next_before"]}
    ).json()
    assert page1["posts"][0]["body"] == "post 24" and page2["posts"][0]["body"] == "post 14"
    pid = page1["posts"][0]["id"]
    assert as_user("asha").post(f"/posts/{pid}/replies", json={"body": "noted"}).status_code == 201
    first = ben.get(f"/workspaces/{sec(ids)}/posts", params={"limit": 1}).json()["posts"][0]
    assert first["replies"][0]["body"] == "noted"


def test_pin_and_official_are_steward_only(as_user, ids):
    ben, asha = as_user("ben"), as_user("asha")
    pid = ben.post(f"/workspaces/{sec(ids)}/posts", json={"body": "pin me"}).json()["id"]
    assert ben.post(f"/posts/{pid}/pin", json={"pinned": True}).status_code == 403
    assert asha.post(f"/posts/{pid}/pin", json={"pinned": True}).status_code == 200
    ben.post(f"/workspaces/{sec(ids)}/posts", json={"body": "newer"})
    feed = ben.get(f"/workspaces/{sec(ids)}/posts").json()
    assert feed["pinned"][0]["id"] == pid and feed["posts"][0]["body"] == "newer"
    assert (
        ben.post(f"/workspaces/{sec(ids)}/posts", json={"body": "o", "kind": "official"}).status_code == 403
    )
    # Inherited member (ben in division) is not a steward there.
    div = ids["workspaces"]["division"]
    assert ben.post(f"/workspaces/{div}/posts", json={"body": "o", "kind": "official"}).status_code == 403
    assert (
        as_user("dana")
        .post(f"/workspaces/{div}/posts", json={"body": "Safety audit", "kind": "official"})
        .status_code
        == 201
    )


def test_moderated_removal_requires_reason(as_user, ids):
    pid = as_user("ben").post(f"/workspaces/{sec(ids)}/posts", json={"body": "off topic"}).json()["id"]
    asha = as_user("asha")
    assert asha.delete(f"/posts/{pid}").status_code == 422
    assert asha.delete(f"/posts/{pid}", params={"reason": "duplicate"}).status_code == 200
    events = as_user("admin").get("/admin/audit").json()["events"]
    assert any(e["action"] == "post.moderate_remove" and e["reason"] == "duplicate" for e in events)
    # Division steward is not a steward in the section.
    pid2 = as_user("ben").post(f"/workspaces/{sec(ids)}/posts", json={"body": "x"}).json()["id"]
    assert as_user("dana").delete(f"/posts/{pid2}", params={"reason": "r"}).status_code == 404


def test_read_only_transition(as_user, ids):
    asha, ben = as_user("asha"), as_user("ben")
    assert (
        ben.patch(f"/workspaces/{sec(ids)}/policy", json={"posting_policy": "read_only"}).status_code == 403
    )
    assert (
        asha.patch(f"/workspaces/{sec(ids)}/policy", json={"posting_policy": "read_only"}).status_code == 200
    )
    r = ben.post(f"/workspaces/{sec(ids)}/posts", json={"body": "blocked"})
    assert r.status_code == 403 and r.json()["error"]["code"] == "workspace_read_only"
    assert (
        ben.post(
            f"/workspaces/{sec(ids)}/chat", json={"body": "blocked", "client_id": "c-123456"}
        ).status_code
        == 403
    )
    assert asha.post(f"/workspaces/{sec(ids)}/posts", json={"body": "steward ok"}).status_code == 201
    asha.patch(f"/workspaces/{sec(ids)}/policy", json={"posting_policy": "open"})
    assert ben.post(f"/workspaces/{sec(ids)}/posts", json={"body": "open again"}).status_code == 201


def test_direct_ids_out_of_scope_look_absent(as_user, ids):
    pid = as_user("ben").post(f"/workspaces/{sec(ids)}/posts", json={"body": "private to A"}).json()["id"]
    chen = as_user("chen")
    unknown = "00000000-0000-0000-0000-000000000001"
    for path in (f"/posts/{pid}/replies", f"/posts/{unknown}/replies"):
        r = chen.post(path, json={"body": "x"})
        assert r.status_code == 404 and r.json()["error"]["code"] == "not_found"
    assert chen.patch(f"/posts/{pid}", json={"body": "x"}).status_code == 404
    assert chen.delete(f"/posts/{pid}").status_code == 404


def test_search_is_scoped(as_user, ids):
    as_user("ben").post(f"/workspaces/{sec(ids)}/posts", json={"body": "ellipsometry results"})
    as_user("chen").post(f"/workspaces/{sec(ids, 'section_b')}/posts", json={"body": "ellipsometry in B"})
    a = as_user("asha").get(f"/workspaces/{sec(ids)}/search", params={"q": "ellipsometry"}).json()
    assert a["counts"]["posts"] == 1 and a["posts"][0]["body"] == "ellipsometry results"
    div = as_user("dana").get(
        f"/workspaces/{ids['workspaces']['division']}/search", params={"q": "ellipsometry"}
    )
    assert div.json()["counts"]["posts"] == 0
    assert (
        as_user("chen").get(f"/workspaces/{sec(ids)}/search", params={"q": "ellipsometry"}).status_code == 404
    )
    wild = as_user("asha").get(f"/workspaces/{sec(ids)}/search", params={"q": "%%"}).json()
    assert wild["counts"]["posts"] == 0


def test_upcoming_and_schedule_validation(as_user, ids):
    ben = as_user("ben")
    r = ben.post(
        f"/workspaces/{sec(ids)}/posts",
        json={
            "body": "Group meeting",
            "due_at": "2031-03-01T10:00:00+00:00",
            "remind_at": "2031-03-01T09:00:00+00:00",
        },
    )
    assert r.status_code == 201
    bad = ben.post(
        f"/workspaces/{sec(ids)}/posts",
        json={"body": "x", "due_at": "2031-03-01T10:00:00+00:00", "remind_at": "2031-03-02T09:00:00+00:00"},
    )
    assert bad.status_code == 422
    naive = ben.post(f"/workspaces/{sec(ids)}/posts", json={"body": "x", "due_at": "2031-03-01T10:00:00"})
    assert naive.status_code == 422
    items = ben.get(f"/workspaces/{sec(ids)}/upcoming").json()["items"]
    assert items[0]["title"] == "Group meeting"
    assert as_user("chen").get(f"/workspaces/{sec(ids)}/upcoming").status_code == 404


def test_mentions_and_official_notifications(as_user, ids):
    as_user("ben").post(f"/workspaces/{sec(ids)}/posts", json={"body": "@asha please review, cc @chen"})
    asha_n = as_user("asha").get("/notifications").json()
    assert asha_n["unread"] == 1 and asha_n["items"][0]["kind"] == "mention"
    assert as_user("chen").get("/notifications").json()["unread"] == 0  # chen cannot read section A
    as_user("dana").post(
        f"/workspaces/{ids['workspaces']['division']}/posts",
        json={"body": "Division notice", "kind": "official"},
    )
    kinds = [n["kind"] for n in as_user("chen").get("/notifications").json()["items"]]
    assert kinds == ["official"]
