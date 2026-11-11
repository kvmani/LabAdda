"""T17/T28: exact workspace ownership, current grants and metadata-only observations."""

import uuid

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import OperationalError

from labadda.models import Asset
from tests.test_chat_board import stroke
from tests.test_files import png_bytes
from tests.test_panel import pair

PDF = b"%PDF-1.4\nworkspace fixture\n%%EOF"


def usage(api, workspace):
    return api.get(f"/workspaces/{workspace}/usage")


def attach(api, workspace, name="private-workspace.pdf", data=PDF, media="application/pdf"):
    result = api.post("/uploads", files={"file": (name, data, media)})
    assert result.status_code == 201
    post = api.post(
        f"/workspaces/{workspace}/posts",
        json={"body": "shared fixture", "attachment_ids": [result.json()["id"]]},
    )
    assert post.status_code == 201
    return result.json(), post.json()


def test_access_follows_actual_workspace_grants_not_admin_or_parent_role(as_user, ids):
    a, b, division = [ids["workspaces"][k] for k in ("section_a", "section_b", "division")]
    assert usage(as_user("ben"), a).status_code == usage(as_user("asha"), a).status_code == 200
    assert usage(as_user("ben"), division).status_code == 200
    for name in ("chen", "dana", "admin", "eli"):
        assert usage(as_user(name), a).status_code == 404
    from labadda.fixtures import fixture_password

    delegated = as_user("admin").post(
        "/admin/usage-readers",
        json={
            "user_id": ids["users"]["dana"],
            "hours": 1,
            "reason": "Synthetic scope regression",
            "password": fixture_password(),
        },
    )
    assert delegated.status_code == 201
    assert as_user("dana").get("/admin/usage").status_code == 200
    assert usage(as_user("dana"), a).status_code == 404
    assert usage(as_user("ben"), b).status_code == 404
    assert usage(as_user("ben"), uuid.uuid4()).json() == usage(as_user("ben"), b).json()
    assert usage(as_user("eli"), ids["workspaces"]["project"]).status_code == 200
    group = ids["workspaces"]["reading_club"]
    assert usage(as_user("ben"), group).status_code == usage(as_user("chen"), group).status_code == 200
    assert usage(as_user("dana"), group).status_code == 404


def test_shared_contributor_files_are_measured_without_private_notes_or_bodies(as_user, ids):
    w = ids["workspaces"]["section_a"]
    ben = as_user("ben")
    asset, post = attach(as_user("asha"), w)
    note = ben.post("/notes", json={"title": "private-note-title", "body": "private-note-body"}).json()
    response = usage(ben, w)
    assert response.status_code == 200 and "no-store" in response.headers["cache-control"]
    result = response.json()
    assert result["files"]["retained_original_bytes"] == len(PDF)
    assert result["files"]["retained_files"] == 1
    assert result["logical_charges"]["by_type"]["post"]["live_items"] == 1
    assert set(result["logical_charges"]["by_type"]) == {"post", "chat", "board_object"}
    for hidden in (
        "private-note-title",
        "private-note-body",
        note["id"],
        asset["id"],
        post["id"],
        asset["display_name"],
        "shared fixture",
    ):
        assert hidden not in response.text
    assert "database" not in result and "filesystem" not in result
    assert result["workspace_budget"]["bytes"] is None and not result["complete_for_enforcement"]


def test_parent_view_never_aggregates_children_or_siblings(as_user, ids):
    a, b, division = [ids["workspaces"][k] for k in ("section_a", "section_b", "division")]
    attach(as_user("ben"), a)
    attach(as_user("chen"), b)
    parent = usage(as_user("dana"), division).json()
    assert parent["files"]["retained_files"] == 0
    assert parent["logical_charges"]["live_logical_bytes"] == 0
    assert usage(as_user("ben"), a).json()["files"]["retained_files"] == 1


def test_removed_post_keeps_retained_file_and_removed_logical_charge(as_user, ids):
    ben = as_user("ben")
    w = ids["workspaces"]["section_a"]
    _, post = attach(ben, w)
    assert ben.delete(f"/posts/{post['id']}").status_code == 200
    result = usage(ben, w).json()
    assert (
        result["files"]["retained_original_bytes"]
        == result["files"]["removed_post_original_bytes"]
        == len(PDF)
    )
    assert result["logical_charges"]["by_type"]["post"]["removed_bytes"] == len("shared fixture")
    assert result["logical_charges"]["by_type"]["post"]["live_items"] == 0


def test_provisional_files_and_pending_capacity_have_no_workspace_attribution(as_user, ids, db_factory):
    ben = as_user("ben")
    w = ids["workspaces"]["section_a"]
    assert (
        ben.post("/uploads", files={"file": ("private-pending.pdf", PDF, "application/pdf")}).status_code
        == 201
    )
    with db_factory() as db:
        db.execute(
            text(
                "insert into upload_reservations(id,user_id,bytes,expires_at) values(gen_random_uuid(),:id,123,now()+interval '10 minutes')"
            ),
            {"id": ids["users"]["ben"]},
        )
        db.commit()
    result = usage(ben, w).json()
    assert result["files"]["retained_files"] == 0 and result["files"]["pending_upload_bytes"] is None
    assert result["files"]["pending_attribution"] == "not_attributed_before_destination_commit"


def test_board_files_and_legacy_preview_unknowns_remain_retained_after_erase(as_user, ids, db_factory):
    ben = as_user("ben")
    w = ids["workspaces"]["section_a"]
    image = ben.post("/uploads", files={"file": ("private-diagram.png", png_bytes(), "image/png")}).json()
    op = {
        "op_id": "workspace-image-01",
        "epoch": 1,
        "type": "add",
        "object_id": "diagram",
        "payload": {"kind": "image", "data": {"x": 0, "y": 0, "w": 40, "h": 40, "asset_id": image["id"]}},
    }
    assert ben.post(f"/workspaces/{w}/board/ops", json=op).status_code == 200
    known = usage(ben, w).json()
    assert known["files"]["recorded_preview_bytes"] > 0
    with db_factory() as db:
        row = db.get(Asset, image["id"])
        row.preview_size = row.preview_sha256 = None
        db.commit()
    assert (
        ben.post(
            f"/workspaces/{w}/board/ops",
            json={"op_id": "workspace-erase-01", "epoch": 1, "type": "erase", "object_id": "diagram"},
        ).status_code
        == 200
    )
    result = usage(ben, w).json()
    assert result["files"]["retained_files"] == 1 and result["files"]["unknown_preview_files"] == 1
    assert result["files"]["recorded_preview_bytes"] == 0
    assert result["logical_charges"]["by_type"]["board_object"]["live_items"] == 0


def test_board_coverage_never_reveals_other_workspace_state(as_user, ids, db_factory):
    a, b = [ids["workspaces"][k] for k in ("section_a", "section_b")]
    assert (
        as_user("chen")
        .post(f"/workspaces/{b}/board/ops", json=stroke("coverage-unknown-01", "fixture-line"))
        .status_code
        == 200
    )
    with db_factory() as db:
        db.execute(text("update boards set charges_epoch=null where workspace_id=:id"), {"id": b})
        db.commit()
    assert usage(as_user("ben"), a).json()["logical_charges"]["board_charges"] == "complete"
    own = usage(as_user("chen"), b).json()["logical_charges"]
    assert own["board_charges"] == "incomplete" and own["unreconciled_boards"] == 1


@pytest.mark.parametrize("revocation,expected", [("membership", 404), ("session", 401), ("identity", 401)])
def test_authority_is_refreshed_after_measurement(
    as_user, ids, db_factory, monkeypatch, revocation, expected
):
    from labadda.api import usage as module

    original = module.workspace_observation
    ben = as_user("ben")
    w = ids["workspaces"]["section_a"]

    def revoke(db, workspace):
        result = original(db, workspace)
        with db_factory() as other:
            if revocation == "membership":
                other.execute(text("delete from memberships where user_id=:id"), {"id": ids["users"]["ben"]})
            elif revocation == "session":
                other.execute(
                    text("update auth_sessions set revoked_at=now() where user_id=:id"),
                    {"id": ids["users"]["ben"]},
                )
            else:
                other.execute(
                    text("update users set is_active=false where id=:id"), {"id": ids["users"]["ben"]}
                )
            other.commit()
        return result

    monkeypatch.setattr(module, "workspace_observation", revoke)
    assert usage(ben, w).status_code == expected


def test_measurement_failure_does_not_return_false_zero(as_user, ids, monkeypatch):
    from labadda.api import usage as module

    def fail(*args):
        raise OperationalError("synthetic unavailable", {}, Exception())

    monkeypatch.setattr(module, "workspace_observation", fail)
    response = usage(as_user("ben"), ids["workspaces"]["section_a"])
    assert response.status_code == 503 and response.json()["error"]["code"] == "measurement_unavailable"
    assert usage(as_user("admin"), ids["workspaces"]["section_a"]).status_code == 404


def test_archived_workspace_remains_measurable_and_panel_never_falls_back(
    as_user, ids, make_client, db_factory
):
    ben = as_user("ben")
    w = ids["workspaces"]["section_a"]
    panel = pair(as_user, make_client, ids)
    assert panel.get(f"/workspaces/{w}/usage").status_code == 401
    assert ben.get(f"/workspaces/{w}/usage", headers={"X-LabAdda-Panel": "1"}).status_code == 401
    with db_factory() as db:
        db.execute(text("update workspaces set archived=true where id=:id"), {"id": w})
        db.commit()
    assert usage(ben, w).status_code == 200
