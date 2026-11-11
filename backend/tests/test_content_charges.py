"""T17 / DL-07: versioned canonical text and board logical charges, and their bounded reconciler."""

import json
import threading
import uuid

import pytest
from alembic import command
from labadda.charge_reconciliation import reconcile_content_charges
from labadda.charges import BOARD_METHOD, TEXT_METHOD, board_key, board_object_bytes
from labadda.cli import alembic_config
from labadda.models import Board, ContentCharge, StorageInspection
from sqlalchemy import create_engine, select, text, update

from .conftest import recreate_schema

MULTIBYTE = "Ångström µm 🧪 薄膜"  # 2-, 2-, 4- and 3-byte UTF-8 characters


def charge(db_factory, item_type, key):
    with db_factory() as db:
        return db.get(ContentCharge, (item_type, str(key)))


def ws(ids, key="section_a"):
    return ids["workspaces"][key]


def stroke(op_id, obj, epoch=1, points=((0, 0), (5, 5))):
    return {
        "op_id": op_id,
        "epoch": epoch,
        "type": "add",
        "object_id": obj,
        "payload": {
            "kind": "stroke",
            "data": {"points": [list(p) for p in points], "color": "#1f2933", "width": 3},
        },
    }


def reconcile(db_factory, **kw):
    return reconcile_content_charges(db_factory, **kw)


# ---- canonical text charges (trigger maintained) ---------------------------


def test_post_reply_chat_and_note_use_utf8_octets(as_user, ids, db_factory):
    ben = as_user("ben")
    post = ben.post(f"/workspaces/{ws(ids)}/posts", json={"body": MULTIBYTE}).json()
    row = charge(db_factory, "post", post["id"])
    assert row.bytes == len(MULTIBYTE.encode()) == 26 and len(MULTIBYTE) == 16  # bytes, not characters
    assert (row.method, row.state, str(row.user_id), str(row.workspace_id)) == (
        TEXT_METHOD,
        "live",
        ids["users"]["ben"],
        ws(ids),
    )
    reply = as_user("asha").post(f"/posts/{post['id']}/replies", json={"body": "ok"}).json()
    assert charge(db_factory, "post", reply["id"]).bytes == 2
    ben.patch(f"/posts/{post['id']}", json={"body": "x" * 7})
    assert charge(db_factory, "post", post["id"]).bytes == 7
    ben.delete(f"/posts/{post['id']}")
    removed = charge(db_factory, "post", post["id"])
    assert (removed.state, removed.bytes) == (
        "removed",
        7,
    )  # body is still stored: charged as removed, not live
    msg = ben.post(f"/workspaces/{ws(ids)}/chat", json={"body": MULTIBYTE, "client_id": "chg-0001"}).json()
    assert charge(db_factory, "chat", msg["id"]).bytes == 26
    note = ben.post("/notes", json={"title": "é", "body": "abc"}).json()
    note_row = charge(db_factory, "note", note["id"])
    assert (note_row.bytes, note_row.workspace_id) == (5, None)
    ben.delete(f"/notes/{note['id']}")
    assert charge(db_factory, "note", note["id"]) is None


def test_usage_reports_own_charges_only(as_user, ids):
    ben, chen = as_user("ben"), as_user("chen")
    ben.post(f"/workspaces/{ws(ids)}/posts", json={"body": "secret plan text"})
    ben.post("/notes", json={"title": "private", "body": "note body"})
    own = ben.get("/usage").json()["logical_charges"]
    assert own["by_type"]["post"]["live_bytes"] == 16 and own["by_type"]["note"]["live_bytes"] == 16
    assert own["methods"] == {"text": TEXT_METHOD, "board": BOARD_METHOD}
    assert own["complete_for_enforcement"] is False and own["unreconciled_boards"] is None
    assert chen.get("/usage").json()["logical_charges"]["live_logical_bytes"] == 0
    site = as_user("admin").get("/admin/usage").json()["logical_charges"]
    assert site["live_logical_bytes"] == 32 and site["board_charges"] == "complete"
    dump = json.dumps(site) + json.dumps(own)
    assert "secret" not in dump and "private" not in dump  # metadata only


def test_contributor_attribution_survives_deactivation(as_user, ids, db_factory):
    post = as_user("ben").post(f"/workspaces/{ws(ids)}/posts", json={"body": "hello"}).json()
    as_user("admin").patch(f"/admin/users/{ids['users']['ben']}", json={"is_active": False})
    assert str(charge(db_factory, "post", post["id"]).user_id) == ids["users"]["ben"]


# ---- board object charges ------------------------------------------------------


def test_board_object_lifecycle(as_user, ids, db_factory):
    ben, asha = as_user("ben"), as_user("asha")
    w = ws(ids)
    ben.post(f"/workspaces/{w}/board/ops", json=stroke("op-ben-001", "s1"))
    key = board_key(uuid.UUID(w), "s1")
    # Charged from the committed payload, where the server normalizes coordinates to floats.
    expected = board_object_bytes(
        "stroke", {"points": [[0.0, 0.0], [5.0, 5.0]], "color": "#1f2933", "width": 3.0}
    )
    row = charge(db_factory, "board_object", key)
    assert (row.bytes, row.method, str(row.user_id)) == (expected, BOARD_METHOD, ids["users"]["ben"])
    sticky = {
        "op_id": "op-ash-001",
        "epoch": 1,
        "type": "add",
        "object_id": "n1",
        "payload": {"kind": "sticky", "data": {"x": 1, "y": 2, "text": MULTIBYTE, "color": "#fff59d"}},
    }
    asha.post(f"/workspaces/{w}/board/ops", json=sticky)
    note_bytes = charge(db_factory, "board_object", board_key(uuid.UUID(w), "n1")).bytes
    assert note_bytes == len(
        json.dumps(
            {"kind": "sticky", "data": {"x": 1.0, "y": 2.0, "text": MULTIBYTE, "color": "#fff59d"}},
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode()
    )
    # Moves do not change the logical charge; erase removes it; undo of the erase restores it.
    asha.post(
        f"/workspaces/{w}/board/ops",
        json={
            "op_id": "op-ash-002",
            "epoch": 1,
            "type": "move",
            "object_id": "n1",
            "payload": {"dx": 10, "dy": 10},
        },
    )
    assert charge(db_factory, "board_object", board_key(uuid.UUID(w), "n1")).bytes == note_bytes
    asha.post(
        f"/workspaces/{w}/board/ops",
        json={"op_id": "op-ash-003", "epoch": 1, "type": "erase", "object_id": "s1"},
    )
    assert charge(db_factory, "board_object", key) is None
    asha.post(f"/workspaces/{w}/board/ops", json={"op_id": "op-ash-004", "epoch": 1, "type": "undo"})
    assert charge(db_factory, "board_object", key).bytes == expected
    # Erasing someone else's object never moves the charge to the eraser.
    assert str(charge(db_factory, "board_object", key).user_id) == ids["users"]["ben"]
    # Restore to empty clears; board stays complete for the new epoch.
    asha.post(f"/workspaces/{w}/board/restore", json={"revision": 0})
    with db_factory() as db:
        assert db.scalars(select(ContentCharge).where(ContentCharge.item_type == "board_object")).all() == []
        board = db.get(Board, uuid.UUID(w))
        assert board.charges_epoch == board.epoch == 2


def test_restore_recharges_restored_objects_to_original_authors(as_user, ids, db_factory):
    ben, asha = as_user("ben"), as_user("asha")
    w = ws(ids)
    rev = ben.post(f"/workspaces/{w}/board/ops", json=stroke("op-ben-001", "keep")).json()["committed"][
        "revision"
    ]
    ben.post(f"/workspaces/{w}/board/ops", json=stroke("op-ben-002", "drop"))
    asha.post(f"/workspaces/{w}/board/restore", json={"revision": rev})
    with db_factory() as db:
        rows = db.scalars(select(ContentCharge).where(ContentCharge.item_type == "board_object")).all()
    assert [(r.item_key, str(r.user_id)) for r in rows] == [
        (board_key(uuid.UUID(w), "keep"), ids["users"]["ben"])
    ]
    assert reconcile(db_factory)["summary"]["issue_count"] == 0


def test_panel_ops_charge_the_pairing_user(as_user, make_client, ids, db_factory):
    code = as_user("ben").post("/panel/pairings", json={"workspace_id": ws(ids)}).json()["code"]
    kiosk = make_client()
    session = kiosk.client.post(kiosk.url("/panel/claim"), json={"code": code}).json()
    kiosk.client.post(
        kiosk.url(f"/workspaces/{ws(ids)}/board/ops"),
        json=stroke("op-panel-01", "p1"),
        headers={"X-LabAdda-Panel": "1", "X-CSRF-Token": session["csrf_token"]},
    )
    row = charge(db_factory, "board_object", board_key(uuid.UUID(ws(ids)), "p1"))
    assert str(row.user_id) == ids["users"]["ben"]


def test_historical_board_is_unknown_until_first_write_or_reconciliation(as_user, ids, db_factory):
    ben = as_user("ben")
    w = ws(ids)
    for i in range(3):
        ben.post(f"/workspaces/{w}/board/ops", json=stroke(f"op-ben-00{i}", f"s{i}"))
    with db_factory() as db:  # simulate a board created before migration 0014
        db.execute(update(Board).values(charges_epoch=None))
        db.execute(text("delete from content_charges where item_type = 'board_object'"))
        db.commit()
    site = as_user("admin").get("/admin/usage").json()["logical_charges"]
    assert site["board_charges"] == "incomplete" and site["unreconciled_boards"] == 1
    assert ben.get("/usage").json()["logical_charges"]["board_charges"] == "incomplete"
    # The next write completes the whole board's ledger, not just the new object.
    ben.post(f"/workspaces/{w}/board/ops", json=stroke("op-ben-010", "s10"))
    with db_factory() as db:
        assert db.scalar(text("select count(*) from content_charges where item_type = 'board_object'")) == 4
    assert as_user("admin").get("/admin/usage").json()["logical_charges"]["board_charges"] == "complete"
    assert reconcile(db_factory)["summary"]["issue_count"] == 0


def test_concurrent_drawing_keeps_ledger_exact(as_user, ids, db_factory):
    w = ws(ids)
    users = [as_user(u) for u in ("ben", "asha")]

    def draw(api, tag):
        for i in range(12):
            api.post(f"/workspaces/{w}/board/ops", json=stroke(f"op-{tag}-{i:03d}", f"{tag}{i}"))
            if i % 3 == 2:
                api.post(
                    f"/workspaces/{w}/board/ops", json={"op_id": f"op-{tag}-u{i}", "epoch": 1, "type": "undo"}
                )

    threads = [threading.Thread(target=draw, args=(u, t)) for u, t in zip(users, ("b", "a"), strict=True)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    result = reconcile(db_factory)
    assert result["summary"]["issue_count"] == 0 and result["summary"]["checked_boards"] == 1


# ---- reconciler -------------------------------------------------------------------


def tamper(db_factory, ids):
    """Bypass the triggers/writers to create every drift class."""
    with db_factory() as db:
        post_ids = [str(r) for r in db.scalars(text("select id from posts order by id"))]
        db.execute(
            text("update content_charges set bytes = bytes + 99 where item_key = :k"), {"k": post_ids[0]}
        )
        db.execute(text("delete from content_charges where item_key = :k"), {"k": post_ids[1]})
        db.execute(
            text(
                "insert into content_charges (item_type, item_key, user_id, workspace_id, method, state, bytes) "
                "values ('chat', :k, :u, :w, 'utf8-text-v1', 'live', 5)"
            ),
            {"k": str(uuid.uuid4()), "u": ids["users"]["ben"], "w": ws(ids)},
        )
        db.execute(
            text("update content_charges set user_id = :u where item_type = 'board_object'"),
            {"u": ids["users"]["dana"]},
        )
        db.commit()


def seed_content(as_user, ids):
    ben = as_user("ben")
    for i in range(3):
        ben.post(f"/workspaces/{ws(ids)}/posts", json={"body": f"post {i} {MULTIBYTE}"})
    ben.post(f"/workspaces/{ws(ids)}/board/ops", json=stroke("op-ben-001", "s1"))


def ledger_snapshot(db_factory):
    with db_factory() as db:
        return sorted(
            (r.item_type, r.item_key, str(r.user_id), r.state, r.bytes)
            for r in db.scalars(select(ContentCharge))
        )


def test_dry_run_reports_every_drift_class_without_mutation(as_user, ids, db_factory):
    seed_content(as_user, ids)
    clean = reconcile(db_factory)
    assert clean["status"] == "completed" and clean["summary"]["issue_count"] == 0
    tamper(db_factory, ids)
    before = ledger_snapshot(db_factory)
    result = reconcile(db_factory)
    s = result["summary"]
    assert s["issue_counts"] == {
        "stale_bytes": 1,
        "missing_charge": 1,
        "orphan_charge": 1,
        "stale_attribution": 1,
    }
    assert s["correction_count"] == 4 and s["applied_count"] == 0 and len(s["plan_digest"]) == 64
    assert ledger_snapshot(db_factory) == before
    assert MULTIBYTE not in json.dumps(result) and "post 0" not in json.dumps(result)
    board_samples = [i["item_key"] for i in s["issues"] if i["item_type"] == "board_object"]
    assert board_samples and all(":sha256:" in k and not k.endswith(":s1") for k in board_samples)


def test_apply_requires_attestation_and_matching_plan(as_user, ids, db_factory):
    seed_content(as_user, ids)
    tamper(db_factory, ids)
    plan = reconcile(db_factory)["summary"]["plan_digest"]
    with pytest.raises(ValueError):
        reconcile(db_factory, apply=True, expected_plan=plan)  # no stopped-writer attestation
    with pytest.raises(ValueError):
        reconcile(db_factory, apply=True, writers_quiesced=True, expected_plan="nope")
    with pytest.raises(ValueError):
        reconcile(db_factory, expected_plan=plan)  # confirmation without apply
    # The plan changes if the ledger drifts again; application refuses and changes nothing.
    with db_factory() as db:
        db.execute(text("update content_charges set bytes = bytes + 1 where item_type = 'board_object'"))
        db.commit()
    before = ledger_snapshot(db_factory)
    stale = reconcile(db_factory, apply=True, writers_quiesced=True, expected_plan=plan)
    assert stale["status"] == "failed" and stale["summary"]["stop_reason"] == "plan_changed"
    assert "plan_digest" not in stale["summary"] and ledger_snapshot(db_factory) == before
    fresh_plan = reconcile(db_factory)["summary"]["plan_digest"]
    applied = reconcile(db_factory, apply=True, writers_quiesced=True, expected_plan=fresh_plan)
    assert applied["status"] == "completed" and applied["summary"]["applied_count"] == 4
    assert reconcile(db_factory)["summary"]["issue_count"] == 0
    events = as_user("admin").get("/admin/audit").json()["events"]
    assert sum(e["action"] == "storage.charge_reconcile" for e in events) >= 4
    with db_factory() as db:
        assert (
            db.scalar(
                select(StorageInspection).where(StorageInspection.id == uuid.UUID(applied["id"]))
            ).status
            == "completed"
        )


def test_apply_completes_historical_boards(as_user, ids, db_factory):
    seed_content(as_user, ids)
    with db_factory() as db:
        db.execute(update(Board).values(charges_epoch=None))
        db.execute(text("delete from content_charges where item_type = 'board_object'"))
        db.commit()
    dry = reconcile(db_factory)["summary"]
    assert dry["boards_to_complete"] == 1 and dry["issue_counts"] == {"missing_charge": 1}
    reconcile(db_factory, apply=True, writers_quiesced=True, expected_plan=dry["plan_digest"])
    with db_factory() as db:
        board = db.scalar(select(Board))
        assert board.charges_epoch == board.epoch
    assert as_user("admin").get("/admin/usage").json()["logical_charges"]["board_charges"] == "complete"


def test_bounded_batches_resume_with_cursors(as_user, ids, db_factory):
    ben = as_user("ben")
    for i in range(5):
        ben.post(f"/workspaces/{ws(ids)}/posts", json={"body": f"p{i}"})
    for key in ("section_a", "division", "reading_club"):
        api = as_user("dana") if key == "division" else ben
        api.post(f"/workspaces/{ws(ids, key)}/board/ops", json=stroke(f"op-{key[:6]}-01", "x"))
    seen_items, seen_boards, cursor_item, cursor_board = 0, 0, None, None
    while True:
        s = reconcile(
            db_factory, max_items=2, max_boards=1, after_item=cursor_item, after_board=cursor_board
        )["summary"]
        assert s["checked_items"] <= 2 and s["checked_boards"] <= 1
        seen_items += s["checked_items"]
        seen_boards += s["checked_boards"]
        cursor_item = s["next_after_item"] or cursor_item
        cursor_board = s["next_after_board"] or cursor_board
        if not s["more_items"] and not s["more_boards"]:
            break
    assert seen_items >= 5 and seen_boards == 3


def test_budget_exhaustion_stops_without_plan(as_user, ids, db_factory, monkeypatch):
    seed_content(as_user, ids)
    stopped = reconcile(db_factory, max_board_objects=1, max_items=1)
    ok = stopped["status"] == "completed"  # one object fits the budget exactly
    assert ok
    ben = as_user("ben")
    ben.post(f"/workspaces/{ws(ids)}/board/ops", json=stroke("op-ben-002", "s2"))
    over = reconcile(db_factory, max_board_objects=1)
    assert over["status"] == "failed" and over["summary"]["stop_reason"] == "board_object_budget_exhausted"
    assert "plan_digest" not in over["summary"]
    from labadda import charge_reconciliation as module

    clock = iter([0.0] + [10_000.0] * 50)
    monkeypatch.setattr(module.time, "monotonic", lambda: next(clock))
    timed = reconcile(db_factory, max_seconds=1)
    assert timed["summary"]["stop_reason"] == "time_budget_exhausted"


def test_invalid_arguments_refused(db_factory, ids):
    for kwargs in (
        {"max_items": 0},
        {"max_seconds": 0},
        {"after_item": "board_object:x"},
        {"after_item": "nocolon"},
    ):
        with pytest.raises(ValueError):
            reconcile(db_factory, **kwargs)


def test_cli_dry_run_and_exit_codes(as_user, ids, db_factory, settings, monkeypatch, capsys):
    from labadda.cli import main

    monkeypatch.setenv("LABADDA_DATABASE_URL", settings.database_url)
    seed_content(as_user, ids)
    assert main(["reconcile-charges"]) == 0
    assert json.loads(capsys.readouterr().out)["summary"]["issue_count"] == 0
    tamper(db_factory, ids)
    assert main(["reconcile-charges"]) == 2
    plan = json.loads(capsys.readouterr().out)["summary"]["plan_digest"]
    assert main(["reconcile-charges", "--apply", "--expected-plan", plan]) == 2  # missing attestation
    assert main(["reconcile-charges", "--apply", "--writers-quiesced", "--expected-plan", plan]) == 0


def test_migration_method_matches_code():
    import importlib.util
    from pathlib import Path

    path = Path(__file__).resolve().parents[1] / "migrations" / "versions" / "0014_content_charges.py"
    spec = importlib.util.spec_from_file_location("m0014", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.TEXT_METHOD == TEXT_METHOD
    assert module.FUNCTIONS.count(TEXT_METHOD) == 1 and module.BACKFILL.count(TEXT_METHOD) == 3


def test_migration_backfills_text_and_leaves_boards_unknown(migrated):
    cfg = alembic_config(migrated)
    recreate_schema(migrated)
    command.upgrade(cfg, "0013")
    engine = create_engine(migrated)
    try:
        with engine.begin() as conn:
            user = conn.execute(
                text(
                    "insert into users (id, username, display_name, is_admin, is_active, must_set_password)"
                    " values (gen_random_uuid(), 'mig', 'Mig', false, true, false) returning id"
                )
            ).scalar()
            space = conn.execute(
                text(
                    "insert into workspaces (id, kind, name, description, archived, posting_policy)"
                    " values (gen_random_uuid(), 'project', 'P', '', false, 'open') returning id"
                )
            ).scalar()
            conn.execute(
                text(
                    "insert into posts (id, workspace_id, author_id, kind, body, pinned)"
                    " values (gen_random_uuid(), :w, :u, 'discussion', :b, false)"
                ),
                {"w": space, "u": user, "b": MULTIBYTE},
            )
            conn.execute(
                text("insert into boards (workspace_id, epoch, revision) values (:w, 1, 7)"), {"w": space}
            )
        command.upgrade(cfg, "head")
        with engine.connect() as conn:
            assert (
                conn.execute(text("select bytes from content_charges where item_type = 'post'")).scalar()
                == 26
            )
            assert conn.execute(text("select charges_epoch from boards")).scalar() is None
        command.downgrade(cfg, "0013")  # derived data: downgrade is allowed and keeps content
        with engine.connect() as conn:
            assert conn.execute(text("select count(*) from posts")).scalar() == 1
    finally:
        engine.dispose()
        recreate_schema(migrated)
        command.upgrade(cfg, "head")
