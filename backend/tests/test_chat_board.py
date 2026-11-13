"""T08, T09 (API level): chat idempotency/replay and board sequencing, undo, conflicts, restore."""

import threading


def ws(ids, key="section_a"):
    return ids["workspaces"][key]


def test_chat_send_replay_and_idempotency(as_user, ids):
    bharat, asha = as_user("bharat"), as_user("asha")
    m1 = bharat.post(
        f"/workspaces/{ws(ids)}/chat", json={"body": "Furnace is free", "client_id": "msg-00001"}
    ).json()
    again = bharat.post(
        f"/workspaces/{ws(ids)}/chat", json={"body": "Furnace is free", "client_id": "msg-00001"}
    ).json()
    assert m1["id"] == again["id"]
    assert (
        bharat.post(
            f"/workspaces/{ws(ids)}/chat", json={"body": "changed", "client_id": "msg-00001"}
        ).status_code
        == 409
    )
    asha.post(f"/workspaces/{ws(ids)}/chat", json={"body": "Thanks", "client_id": "msg-00002"})
    replay = bharat.get(f"/workspaces/{ws(ids)}/chat", params={"after": m1["seq"]}).json()["messages"]
    assert [m["body"] for m in replay] == ["Thanks"]
    names = {w["name"]: w for w in bharat.get("/workspaces").json()["workspaces"]}
    assert names["Thin Films Section"]["unread_chat"] == 1
    bharat.post(f"/workspaces/{ws(ids)}/chat/read", json={"seq": replay[-1]["seq"]})
    names = {w["name"]: w for w in bharat.get("/workspaces").json()["workspaces"]}
    assert names["Thin Films Section"]["unread_chat"] == 0
    assert as_user("chitra").get(f"/workspaces/{ws(ids)}/chat").status_code == 404


def test_chat_history_pagination(as_user, ids):
    bharat = as_user("bharat")
    for i in range(12):
        bharat.post(f"/workspaces/{ws(ids)}/chat", json={"body": f"m{i}", "client_id": f"page-{i:05d}"})
    last = bharat.get(f"/workspaces/{ws(ids)}/chat", params={"limit": 5}).json()
    assert [m["body"] for m in last["messages"]] == ["m7", "m8", "m9", "m10", "m11"] and last["has_more"]
    older = bharat.get(
        f"/workspaces/{ws(ids)}/chat", params={"limit": 5, "before": last["messages"][0]["seq"]}
    ).json()
    assert older["messages"][-1]["body"] == "m6"


def stroke(op_id, obj, epoch=1, pts=((0, 0), (10, 10))):
    return {
        "op_id": op_id,
        "epoch": epoch,
        "type": "add",
        "object_id": obj,
        "payload": {
            "kind": "stroke",
            "data": {"points": [list(p) for p in pts], "color": "#1f2933", "width": 3},
        },
    }


def test_board_ops_retry_conflict_and_replay(as_user, ids):
    bharat, asha = as_user("bharat"), as_user("asha")
    w = ws(ids)
    r1 = bharat.post(f"/workspaces/{w}/board/ops", json=stroke("op-bharat-001", "s1")).json()
    retry = bharat.post(f"/workspaces/{w}/board/ops", json=stroke("op-bharat-001", "s1")).json()
    assert retry["duplicate"] and retry["committed"]["revision"] == r1["committed"]["revision"]
    changed = bharat.post(f"/workspaces/{w}/board/ops", json=stroke("op-bharat-001", "s1", pts=((5, 5),)))
    assert changed.status_code == 409 and changed.json()["error"]["code"] == "op_id_reused"
    # Same op_id from another actor is a different operation.
    assert asha.post(f"/workspaces/{w}/board/ops", json=stroke("op-bharat-001", "s2")).status_code == 200
    state = asha.get(
        f"/workspaces/{w}/board", params={"epoch": 1, "after": r1["committed"]["revision"]}
    ).json()
    assert [o["object_id"] for o in state["ops"]] == ["s2"] and state["reset"] is False
    assert as_user("chitra").get(f"/workspaces/{w}/board").status_code == 404
    bad = bharat.post(
        f"/workspaces/{w}/board/ops",
        json={
            **stroke("op-bharat-x01", "s9"),
            "payload": {"kind": "stroke", "data": {"points": [], "color": "#1f2933"}},
        },
    )
    assert bad.status_code == 422


def test_undo_is_own_only_and_erase_is_distinct(as_user, ids):
    bharat, asha = as_user("bharat"), as_user("asha")
    w = ws(ids)
    bharat.post(f"/workspaces/{w}/board/ops", json=stroke("op-bharat-001", "bharat-stroke"))
    asha.post(f"/workspaces/{w}/board/ops", json=stroke("op-ash-001", "asha-stroke"))
    # Bharat erases Asha's stroke (a distinct mutation).
    assert (
        bharat.post(
            f"/workspaces/{w}/board/ops",
            json={"op_id": "op-bharat-002", "epoch": 1, "type": "erase", "object_id": "asha-stroke"},
        ).status_code
        == 200
    )
    again = asha.post(
        f"/workspaces/{w}/board/ops",
        json={"op_id": "op-ash-002", "epoch": 1, "type": "erase", "object_id": "asha-stroke"},
    )
    assert again.status_code == 409 and again.json()["error"]["code"] == "object_gone"
    # Asha's undo reverses only Asha's own most recent op (her add), not Bharat's erase.
    u = asha.post(
        f"/workspaces/{w}/board/ops", json={"op_id": "op-ash-003", "epoch": 1, "type": "undo"}
    ).json()
    assert u["committed"]["object_id"] == "asha-stroke"
    # Bharat's undo reverses his erase.
    u2 = bharat.post(
        f"/workspaces/{w}/board/ops", json={"op_id": "op-bharat-003", "epoch": 1, "type": "undo"}
    ).json()
    assert u2["committed"]["payload"]["target_revision"] == 3
    assert as_user("deepa").get(f"/workspaces/{ids['workspaces']['division']}/board").status_code == 200


def test_stale_move_rejected(as_user, ids):
    bharat, asha = as_user("bharat"), as_user("asha")
    w = ws(ids)
    rev = bharat.post(
        f"/workspaces/{w}/board/ops",
        json={
            "op_id": "op-bharat-001",
            "epoch": 1,
            "type": "add",
            "object_id": "note-1",
            "payload": {"kind": "sticky", "data": {"x": 0, "y": 0, "text": "Agenda", "color": "#fff59d"}},
        },
    ).json()
    base = rev["committed"]["revision"]
    assert (
        asha.post(
            f"/workspaces/{w}/board/ops",
            json={
                "op_id": "op-ash-001",
                "epoch": 1,
                "type": "move",
                "object_id": "note-1",
                "base_revision": base,
                "payload": {"dx": 5, "dy": 5},
            },
        ).status_code
        == 200
    )
    stale = bharat.post(
        f"/workspaces/{w}/board/ops",
        json={
            "op_id": "op-bharat-002",
            "epoch": 1,
            "type": "move",
            "object_id": "note-1",
            "base_revision": base,
            "payload": {"dx": 1, "dy": 1},
        },
    )
    assert stale.status_code == 409 and stale.json()["error"]["code"] == "stale_object"


def test_restore_new_epoch_rejects_old(as_user, ids):
    bharat, asha = as_user("bharat"), as_user("asha")
    w = ws(ids)
    first = bharat.post(f"/workspaces/{w}/board/ops", json=stroke("op-bharat-001", "keep")).json()[
        "committed"
    ]["revision"]
    bharat.post(f"/workspaces/{w}/board/ops", json=stroke("op-bharat-002", "drop"))
    assert bharat.post(f"/workspaces/{w}/board/restore", json={"revision": first}).status_code == 403
    r = asha.post(f"/workspaces/{w}/board/restore", json={"revision": first, "reason": "accidental scribble"})
    assert r.status_code == 200 and r.json()["epoch"] == 2
    state = bharat.get(f"/workspaces/{w}/board").json()
    assert state["epoch"] == 2 and [o["object_id"] for o in state["ops"]] == ["keep"]
    stale = bharat.post(f"/workspaces/{w}/board/ops", json=stroke("op-bharat-003", "late", epoch=1))
    assert stale.status_code == 409 and stale.json()["error"]["code"] == "stale_epoch"
    # A pre-restore retry of an op committed in epoch 1 still returns its original result.
    assert (
        bharat.post(f"/workspaces/{w}/board/ops", json=stroke("op-bharat-002", "drop")).json()["duplicate"]
        is True
    )


def test_parallel_drawing_sequences_without_gaps(as_user, ids):
    w = ws(ids)
    users = [as_user(u) for u in ("bharat", "asha")]
    errors = []

    def draw(api, tag):
        for i in range(10):
            r = api.post(f"/workspaces/{w}/board/ops", json=stroke(f"op-{tag}-{i:03d}", f"{tag}-{i}"))
            if r.status_code != 200:
                errors.append(r.text)

    threads = [threading.Thread(target=draw, args=(u, t)) for u, t in zip(users, ("b", "a"), strict=False)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert not errors
    revs = [o["revision"] for o in users[0].get(f"/workspaces/{w}/board").json()["ops"]]
    assert revs == list(range(1, 21))
