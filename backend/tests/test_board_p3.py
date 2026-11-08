"""T08/T09/T10 completion: board images, snapshots, compaction, restart recovery, live revocation."""

import io
import threading
import time
from dataclasses import replace

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from labadda.app import create_app
from labadda.boardstate import compact
from labadda.models import Board

from .test_files import png_bytes


def ws(ids, key="section_a"):
    return ids["workspaces"][key]


def stroke(op_id, obj, epoch=1, pts=((10, 10), (60, 40)), color="#c62828"):
    return {"op_id": op_id, "epoch": epoch, "type": "add", "object_id": obj,
            "payload": {"kind": "stroke", "data": {"points": [list(p) for p in pts], "color": color, "width": 4}}}


def upload_png(api):
    r = api.post("/uploads", files={"file": ("photo.png", png_bytes(), "image/png")})
    assert r.status_code == 201
    return r.json()["id"]


def image_op(op_id, obj, asset_id, epoch=1):
    return {"op_id": op_id, "epoch": epoch, "type": "add", "object_id": obj,
            "payload": {"kind": "image", "data": {"x": 100, "y": 100, "w": 80, "h": 60, "asset_id": asset_id}}}


# ---- images on the board ---------------------------------------------------

def test_embed_image_and_scope(as_user, ids):
    ben, asha = as_user("ben"), as_user("asha")
    asset = upload_png(ben)
    # Someone else's provisional upload cannot be placed.
    assert asha.post(f"/workspaces/{ws(ids)}/board/ops", json=image_op("op-ash-img1", "img-x", asset)).status_code == 422
    r = ben.post(f"/workspaces/{ws(ids)}/board/ops", json=image_op("op-ben-img1", "img-1", asset))
    assert r.status_code == 200
    # Board image is readable by board readers (including the inherited division steward) and nobody else.
    assert asha.get(f"/files/{asset}/preview").status_code == 200
    assert as_user("dana").get(f"/files/{asset}/preview").status_code == 404  # dana cannot read section A
    for user in ("chen", "admin", "eli"):
        assert as_user(user).get(f"/files/{asset}").status_code == 404
    # The asset is now owned by the board: it cannot be attached to a post or placed on another board.
    assert ben.post(f"/workspaces/{ws(ids)}/posts", json={"body": "x", "attachment_ids": [asset]}).status_code == 422
    div = ws(ids, "division")
    assert ben.post(f"/workspaces/{div}/board/ops", json=image_op("op-ben-img2", "img-2", asset)).status_code == 422
    # Re-placing on the same board is allowed (e.g. a copy after erase).
    assert ben.post(f"/workspaces/{ws(ids)}/board/ops", json=image_op("op-ben-img3", "img-3", asset)).status_code == 200


def test_non_image_cannot_be_placed(as_user, ids):
    ben = as_user("ben")
    pdf = ben.post("/uploads", files={"file": ("a.pdf", b"%PDF-1.4\n%%EOF\n", "application/pdf")}).json()["id"]
    assert ben.post(f"/workspaces/{ws(ids)}/board/ops", json=image_op("op-ben-pdf1", "p", pdf)).status_code == 422


# ---- render and snapshot publishing ---------------------------------------

def test_render_preview_is_scoped(as_user, ids):
    ben = as_user("ben")
    rev = ben.post(f"/workspaces/{ws(ids)}/board/ops", json=stroke("op-ben-001", "s1")).json()["committed"]["revision"]
    params = {"revision": rev, "x": 0, "y": 0, "w": 100, "h": 50}
    r = ben.get(f"/workspaces/{ws(ids)}/board/render", params=params)
    assert r.status_code == 200 and r.headers["content-type"] == "image/png"
    img = Image.open(io.BytesIO(r.content)).convert("RGB")
    assert img.size == (100, 50) and img.getpixel((35, 25)) != (255, 255, 255)
    empty = Image.open(io.BytesIO(ben.get(f"/workspaces/{ws(ids)}/board/render",
                                          params={**params, "revision": 0}).content)).convert("RGB")
    assert empty.getextrema() == ((255, 255), (255, 255), (255, 255))
    assert as_user("chen").get(f"/workspaces/{ws(ids)}/board/render", params=params).status_code == 404
    assert ben.get(f"/workspaces/{ws(ids)}/board/render", params={**params, "revision": rev + 5}).status_code == 422


def publish(api, src, dest, revision, client_id="snap-0001", confirm=None, summary="Board summary"):
    body = {"revision": revision, "region": {"x": 0, "y": 0, "w": 200, "h": 120}, "destination_id": dest,
            "summary": summary, "client_id": client_id}
    if confirm:
        body["confirm_audience"] = confirm
    return api.post(f"/workspaces/{src}/board/snapshots", json=body)


def test_snapshot_same_workspace_is_fixed_copy(as_user, ids):
    ben = as_user("ben")
    src = ws(ids)
    rev = ben.post(f"/workspaces/{src}/board/ops", json=stroke("op-ben-001", "s1")).json()["committed"]["revision"]
    r = publish(ben, src, src, rev)
    assert r.status_code == 201
    retry = publish(ben, src, src, rev)
    assert retry.json()["duplicate"] and retry.json()["post_id"] == r.json()["post_id"]
    assert publish(ben, src, src, rev, summary="changed").status_code == 409
    post = ben.get(f"/workspaces/{src}/posts").json()["posts"][0]
    assert post["snapshot"]["source_revision"] == rev and post["snapshot"]["source_name"] == "Thin Films Section"
    att = post["attachments"][0]
    before = ben.get(f"/files/{att['id']}").content
    # Editing or erasing the source board does not change the published copy.
    ben.post(f"/workspaces/{src}/board/ops", json={"op_id": "op-ben-002", "epoch": 1, "type": "erase", "object_id": "s1"})
    ben.post(f"/workspaces/{src}/board/ops", json=stroke("op-ben-003", "s2", pts=((0, 0), (200, 120))))
    assert ben.get(f"/files/{att['id']}").content == before
    events = as_user("admin").get("/admin/audit").json()["events"]
    assert any(e["action"] == "board.snapshot_publish" for e in events)


def test_parent_publish_needs_confirmation_and_is_target_owned(as_user, ids):
    ben = as_user("ben")
    src, div = ws(ids), ws(ids, "division")
    dests = ben.get(f"/workspaces/{src}/board/snapshot-destinations").json()["destinations"]
    assert [d["name"] for d in dests][:2] == ["Thin Films Section", "Surface Science Division"]
    rev = ben.post(f"/workspaces/{src}/board/ops", json=stroke("op-ben-001", "s1")).json()["committed"]["revision"]
    r = publish(ben, src, div, rev)
    assert r.status_code == 422 and r.json()["error"]["code"] == "confirmation_required"
    assert publish(ben, src, div, rev, confirm=src).status_code == 422  # must name the destination
    ok = publish(ben, src, div, rev, confirm=div)
    assert ok.status_code == 201
    # Chen (sibling section) reads the division copy but learns nothing about the source.
    chen_post = as_user("chen").get(f"/workspaces/{div}/posts").json()["posts"][0]
    assert chen_post["snapshot"] == {"source_revision": rev, "source_name": None, "source_workspace_id": None}
    assert as_user("chen").get(f"/files/{chen_post['attachments'][0]['id']}").status_code == 200
    assert as_user("chen").get(f"/workspaces/{src}/board").status_code == 404
    # Removing the source board's content or Ben's access leaves the published copy intact.
    as_user("asha").post(f"/workspaces/{src}/board/restore", json={"revision": 0})
    as_user("admin").delete(f"/admin/workspaces/{src}/memberships/{ids['users']['ben']}")
    assert as_user("dana").get(f"/workspaces/{div}/posts").json()["posts"][0]["id"] == ok.json()["post_id"]


def test_publish_scope_rules(as_user, ids):
    ben, chen = as_user("ben"), as_user("chen")
    src = ws(ids)
    rev = ben.post(f"/workspaces/{src}/board/ops", json=stroke("op-ben-001", "s1")).json()["committed"]["revision"]
    # Sibling and unrelated destinations look absent.
    assert publish(ben, src, ws(ids, "section_b"), rev, confirm=ws(ids, "section_b")).status_code == 404
    assert publish(ben, src, ws(ids, "project"), rev, confirm=ws(ids, "project")).status_code == 404
    # Groups publish only within the group.
    group = ws(ids, "reading_club")
    grev = chen.post(f"/workspaces/{group}/board/ops", json=stroke("op-chen-01", "g1")).json()["committed"]["revision"]
    assert len(chen.get(f"/workspaces/{group}/board/snapshot-destinations").json()["destinations"]) == 1
    assert publish(chen, group, ws(ids, "section_b"), grev, confirm=ws(ids, "section_b")).status_code == 404
    # Non-readers of the source cannot publish from it.
    assert publish(chen, src, src, rev).status_code == 404
    # A read-only destination refuses ordinary members.
    div = ws(ids, "division")
    as_user("dana").patch(f"/workspaces/{div}/policy", json={"posting_policy": "read_only"})
    r = publish(ben, src, div, rev, client_id="snap-0002", confirm=div)
    assert r.status_code == 404  # not offered as a writable destination
    assert all(d["name"] != "Surface Science Division"
               for d in ben.get(f"/workspaces/{src}/board/snapshot-destinations").json()["destinations"])


# ---- compaction ------------------------------------------------------------

def test_compaction_replay_and_undo(as_user, ids, db_factory):
    ben, asha = as_user("ben"), as_user("asha")
    w = ws(ids)
    ben.post(f"/workspaces/{w}/board/ops", json=stroke("op-ben-000", "early"))
    ben.post(f"/workspaces/{w}/board/ops", json={"op_id": "op-ben-u00", "epoch": 1, "type": "undo"})  # undoes "early"
    for i in range(28):
        asha.post(f"/workspaces/{w}/board/ops", json=stroke(f"op-ash-{i:03d}", f"a{i}"))
    full = ben.get(f"/workspaces/{w}/board").json()
    assert full["revision"] == 30 and len(full["ops"]) == 30
    with db_factory() as db:
        import uuid
        board = db.get(Board, uuid.UUID(w), with_for_update=True)
        assert compact(db, board, keep=10) == 20
        db.commit()
    snap = ben.get(f"/workspaces/{w}/board").json()
    assert snap["base_revision"] == 20 and snap["reset"] and snap["snapshot"]["revision"] == 20
    assert [o["revision"] for o in snap["ops"]] == list(range(21, 31))
    assert snap["snapshot"]["objects"]["early"]["alive"] is False
    # Replay from before the base falls back to the snapshot; from above it replays.
    assert ben.get(f"/workspaces/{w}/board", params={"epoch": 1, "after": 5}).json()["reset"] is True
    replay = ben.get(f"/workspaces/{w}/board", params={"epoch": 1, "after": 25}).json()
    assert replay["reset"] is False and [o["revision"] for o in replay["ops"]] == [26, 27, 28, 29, 30]
    # Ben's only ops were compacted: nothing left to undo. Asha can undo her retained op.
    r = ben.post(f"/workspaces/{w}/board/ops", json={"op_id": "op-ben-u01", "epoch": 1, "type": "undo"})
    assert r.status_code == 409 and r.json()["error"]["code"] == "nothing_to_undo"
    u = asha.post(f"/workspaces/{w}/board/ops", json={"op_id": "op-ash-u01", "epoch": 1, "type": "undo"}).json()
    assert u["committed"]["object_id"] == "a27"
    # Restore to a compacted, non-snapshot revision is refused; the snapshot revision works.
    r = asha.post(f"/workspaces/{w}/board/restore", json={"revision": 12})
    assert r.status_code == 422 and r.json()["error"]["code"] == "revision_compacted"
    assert asha.post(f"/workspaces/{w}/board/restore", json={"revision": 20}).status_code == 200
    restored = ben.get(f"/workspaces/{w}/board").json()
    assert sorted(o["object_id"] for o in restored["ops"]) == sorted(f"a{i}" for i in range(18))


def test_scheduled_compaction(as_user, ids, db_factory):
    from labadda.boardstate import compact_all
    ben = as_user("ben")
    for i in range(12):
        ben.post(f"/workspaces/{ws(ids)}/board/ops", json=stroke(f"op-ben-{i:03d}", f"s{i}"))
    with db_factory() as db:
        assert compact_all(db, threshold=10, keep=4) == 1
    with db_factory() as db:
        assert compact_all(db, threshold=10, keep=4) == 0
    assert ben.get(f"/workspaces/{ws(ids)}/board").json()["base_revision"] == 8


# ---- restart recovery (T08) and live revocation (T10) -----------------------

def test_restart_between_commit_and_fanout(settings, ids, make_client):
    """Commit succeeds but the process dies before fanout; a restarted server serves the op by replay."""
    from labadda.fixtures import fixture_password
    first = create_app(settings)
    first.state.hub.loop = None  # no event loop: fanout is lost, as in a crash right after commit
    with TestClient(first) as c:
        login = c.post(f"{settings.api_prefix}/auth/login", json={"username": "ben", "password": fixture_password()})
        h = {"X-CSRF-Token": login.json()["csrf_token"]}
        first.state.hub.loop = None
        r = c.post(f"{settings.api_prefix}/workspaces/{ws(ids)}/board/ops", json=stroke("op-ben-001", "s1"), headers=h)
        assert r.status_code == 200
        c.post(f"{settings.api_prefix}/workspaces/{ws(ids)}/chat",
               json={"body": "before crash", "client_id": "crash-0001"}, headers=h)
    restarted = create_app(settings)
    with TestClient(restarted) as c2:
        c2.post(f"{settings.api_prefix}/auth/login", json={"username": "asha", "password": fixture_password()})
        board = c2.get(f"{settings.api_prefix}/workspaces/{ws(ids)}/board", params={"epoch": 1, "after": 0}).json()
        assert [o["object_id"] for o in board["ops"]] == ["s1"]
        chat = c2.get(f"{settings.api_prefix}/workspaces/{ws(ids)}/chat", params={"after": 0}).json()
        assert [m["body"] for m in chat["messages"]] == ["before crash"]
    # A client retrying its pending op after restart gets the committed result, not a duplicate.
    ben = make_client("ben")
    again = ben.post(f"/workspaces/{ws(ids)}/board/ops", json=stroke("op-ben-001", "s1")).json()
    assert again["duplicate"] is True and again["committed"]["revision"] == 1


def test_revocation_under_live_traffic(as_user, ids, settings):
    ben, asha = as_user("ben"), as_user("asha")
    a = ws(ids)
    stop = threading.Event()
    sent = []

    def talk():
        i = 0
        while not stop.is_set():
            body = f"traffic {i}"
            if asha.post(f"/workspaces/{a}/chat", json={"body": body, "client_id": f"live-{i:06d}"}).status_code == 201:
                sent.append(body)
            i += 1
            time.sleep(0.01)

    with ben.client.websocket_connect(f"{settings.base_path}/ws/") as conn:
        conn.receive_json()
        conn.send_json({"type": "subscribe", "workspace_id": a})
        while conn.receive_json()["type"] != "subscribed":
            pass
        t = threading.Thread(target=talk)
        t.start()
        received_before = 0
        while received_before < 5:
            if conn.receive_json()["type"] == "chat.message":
                received_before += 1
        as_user("admin").delete(f"/admin/workspaces/{a}/memberships/{ids['users']['ben']}")
        seen_revoked = False
        leaked = []
        deadline = time.time() + 3
        while time.time() < deadline:
            msg = conn.receive_json()
            if msg["type"] == "revoked":
                seen_revoked = True
                stop.set()
                conn.send_json({"type": "ping"})
            elif msg["type"] == "chat.message" and seen_revoked:
                leaked.append(msg)
            elif msg["type"] == "pong":
                break
        t.join()
    assert seen_revoked and leaked == []
    assert len(sent) > 5
    assert ben.get(f"/workspaces/{a}/chat").status_code == 404


def test_state_cache_matches_rebuild_under_concurrency(as_user, ids, db_factory):
    import uuid

    from labadda.boardstate import state_at, state_cache
    w = ws(ids)
    users = [as_user(u) for u in ("ben", "asha")]

    def draw(api, tag):
        for i in range(15):
            api.post(f"/workspaces/{w}/board/ops", json=stroke(f"op-{tag}-{i:03d}", f"{tag}-{i}"))
            if i % 4 == 3:
                api.post(f"/workspaces/{w}/board/ops", json={"op_id": f"op-{tag}-u{i:02d}", "epoch": 1, "type": "undo"})

    threads = [threading.Thread(target=draw, args=(u, t)) for u, t in zip(users, ("b", "a"))]
    [t.start() for t in threads]
    [t.join() for t in threads]
    users[1].post(f"/workspaces/{w}/board/ops", json={"op_id": "op-a-erase", "epoch": 1, "type": "erase",
                                                     "object_id": "b-0"})
    with db_factory() as db:
        board = db.get(Board, uuid.UUID(w))
        assert state_cache.objects(db, board) == state_at(db, board)
    # After a restore (new epoch) the cache is rebuilt, never reused.
    users[1].post(f"/workspaces/{w}/board/restore", json={"revision": 0})
    with db_factory() as db:
        board = db.get(Board, uuid.UUID(w))
        assert state_cache.objects(db, board) == {} == state_at(db, board)


def _paused_fold(monkeypatch):
    """Make compaction's fold signal that it started, then wait until released."""
    from labadda import boardstate
    started, release = threading.Event(), threading.Event()
    real = boardstate.state_at

    def paused(db, board, revision=None):
        started.set()
        assert release.wait(10)
        return real(db, board, revision)

    monkeypatch.setattr(boardstate, "state_at", paused)
    return started, release, real


def test_drawing_continues_while_compaction_folds(as_user, ids, db_factory, monkeypatch):
    from labadda import boardstate
    ben = as_user("ben")
    w = ws(ids)
    for i in range(12):
        ben.post(f"/workspaces/{w}/board/ops", json=stroke(f"op-ben-{i:03d}", f"s{i}"))
    started, release, real = _paused_fold(monkeypatch)
    result = {}
    worker = threading.Thread(target=lambda: result.update(n=boardstate.compact_all(db_factory(), threshold=10,
                                                                                     keep=4)))
    worker.start()
    assert started.wait(5)
    # The fold is in progress; the board row is not locked, so a new stroke commits immediately.
    monkeypatch.setattr(boardstate, "state_at", real)  # the API's own reads must not pause
    t0 = time.monotonic()
    r = ben.post(f"/workspaces/{w}/board/ops", json=stroke("op-ben-during", "during"))
    assert r.status_code == 200 and time.monotonic() - t0 < 2
    release.set()
    worker.join(10)
    assert result["n"] == 1
    board = ben.get(f"/workspaces/{w}/board").json()
    assert board["base_revision"] == 8
    alive = set(board["snapshot"]["objects"]) | {o["object_id"] for o in board["ops"]}
    assert {f"s{i}" for i in range(12)} | {"during"} <= alive


def test_compaction_skips_a_board_restored_during_the_fold(as_user, ids, db_factory, monkeypatch):
    from labadda import boardstate
    ben, asha = as_user("ben"), as_user("asha")
    w = ws(ids)
    for i in range(12):
        ben.post(f"/workspaces/{w}/board/ops", json=stroke(f"op-ben-{i:03d}", f"s{i}"))
    started, release, real = _paused_fold(monkeypatch)
    result = {}
    worker = threading.Thread(target=lambda: result.update(n=boardstate.compact_all(db_factory(), threshold=10,
                                                                                     keep=4)))
    worker.start()
    assert started.wait(5)
    monkeypatch.setattr(boardstate, "state_at", real)
    assert asha.post(f"/workspaces/{w}/board/restore", json={"revision": 0}).status_code == 200
    release.set()
    worker.join(10)
    assert result["n"] == 0  # stale epoch: no snapshot written from the old fold
    board = ben.get(f"/workspaces/{w}/board").json()
    assert board["epoch"] == 2 and board["snapshot"] is None and board["ops"] == []


def test_state_cache_survives_compaction_without_refold(as_user, ids, db_factory, monkeypatch):
    import uuid

    from labadda import boardstate
    from labadda.boardstate import compact_all, state_cache
    ben = as_user("ben")
    w = ws(ids)
    for i in range(12):
        ben.post(f"/workspaces/{w}/board/ops", json=stroke(f"op-ben-{i:03d}", f"s{i}"))
    with db_factory() as db:
        assert compact_all(db, threshold=10, keep=4) == 1

    def refold(*_args, **_kwargs):
        raise AssertionError("cache should not refold after compaction")

    monkeypatch.setattr(boardstate, "state_at", refold)
    assert ben.post(f"/workspaces/{w}/board/ops", json=stroke("op-ben-after", "after")).status_code == 200
    with db_factory() as db:
        board = db.get(Board, uuid.UUID(w))
        assert "after" in state_cache.objects(db, board)
