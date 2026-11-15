"""Workspace whiteboard tabs: multiple tabs per workspace, title renaming, op isolation and limits."""


def test_tabbed_workspace_whiteboards(as_user, ids):
    """Multiple tabbed whiteboards on a workspace maintain independent titles and revisions."""
    bharat = as_user("bharat")
    ws_id = ids["workspaces"]["section_a"]

    # 1. Fetch initial board tabs
    tabs_res = bharat.get(f"/workspaces/{ws_id}/boards")
    assert tabs_res.status_code == 200
    tabs = tabs_res.json()["boards"]
    assert len(tabs) >= 1
    assert tabs[0]["board_index"] == 0
    assert tabs[0]["title"] == "WhiteBoard_1"

    # 2. Rename tab 0 and create/rename tab 1 and tab 2 with short names (<= 10 chars)
    r_ren0 = bharat.patch(f"/workspaces/{ws_id}/boards/0", json={"title": "SiC Proj"})
    assert r_ren0.status_code == 200
    assert r_ren0.json()["title"] == "SiC Proj"

    r_ren1 = bharat.patch(f"/workspaces/{ws_id}/boards/1", json={"title": "AdminBoard"})
    assert r_ren1.status_code == 200
    assert r_ren1.json()["title"] == "AdminBoard"

    r_ren2 = bharat.patch(f"/workspaces/{ws_id}/boards/2", json={"title": "Lab_Setup"})
    assert r_ren2.status_code == 200
    assert r_ren2.json()["title"] == "Lab_Setup"

    # 3. Verify all 3 tabs are listed
    tabs_after = bharat.get(f"/workspaces/{ws_id}/boards").json()["boards"]
    titles_by_idx = {t["board_index"]: t["title"] for t in tabs_after}
    assert titles_by_idx[0] == "SiC Proj"
    assert titles_by_idx[1] == "AdminBoard"
    assert titles_by_idx[2] == "Lab_Setup"

    # Custom names > 10 chars are rejected with 422
    assert bharat.patch(f"/workspaces/{ws_id}/boards/0", json={"title": "LongBoardName"}).status_code == 422

    # Resetting to default WhiteBoard_1 is allowed
    r_reset = bharat.patch(f"/workspaces/{ws_id}/boards/0", json={"title": "WhiteBoard_1"})
    assert r_reset.status_code == 200
    assert r_reset.json()["title"] == "WhiteBoard_1"

    # 4. Submit operation on Board 1
    op_body = {
        "op_id": "op-test-tab1-001",
        "epoch": 1,
        "type": "add",
        "object_id": "txt-001",
        "board_index": 1,
        "payload": {
            "kind": "text",
            "data": {"x": 50, "y": 60, "text": "Chamber vacuum level: 10^-6 Torr", "color": "#1f2933"},
        },
    }
    r_op = bharat.post(f"/workspaces/{ws_id}/board/ops", json=op_body)
    assert r_op.status_code == 200
    committed = r_op.json()["committed"]
    assert committed["revision"] == 1
    assert committed["board_index"] == 1

    # 5. Read Board 1 and Board 0, verifying complete isolation
    b1_state = bharat.get(f"/workspaces/{ws_id}/board?board_index=1").json()
    assert b1_state["revision"] == 1
    assert len(b1_state["ops"]) == 1
    assert b1_state["ops"][0]["object_id"] == "txt-001"

    b0_state = bharat.get(f"/workspaces/{ws_id}/board?board_index=0").json()
    assert b0_state["revision"] == 0
    assert len(b0_state["ops"]) == 0

    # 6. Denial check: Out-of-workspace user cannot read or write to secondary boards
    outsider = as_user("chitra")  # chitra is not in section_a
    assert outsider.get(f"/workspaces/{ws_id}/board?board_index=1").status_code == 404
    assert outsider.get(f"/workspaces/{ws_id}/boards").status_code == 404


def test_admin_configurable_whiteboards_setting(as_user):
    """Administrator can configure maximum allowed whiteboards per scope."""
    admin = as_user("admin")
    bharat = as_user("bharat")

    # 1. Read default setting
    r_get = admin.get("/admin/settings/whiteboards")
    assert r_get.status_code == 200
    data = r_get.json()
    assert data["max_whiteboards_per_scope"] == 5

    # 2. Non-admin is denied
    assert bharat.get("/admin/settings/whiteboards").status_code == 403
    r_bad = bharat.patch("/admin/settings/whiteboards", json={"max_whiteboards_per_scope": 8})
    assert r_bad.status_code == 403

    # 3. Admin updates setting to 8
    r_patch = admin.patch("/admin/settings/whiteboards", json={"max_whiteboards_per_scope": 8})
    assert r_patch.status_code == 200
    assert r_patch.json()["max_whiteboards_per_scope"] == 8

    # 4. Verify updated setting in capabilities
    cap_res = bharat.get("/capabilities").json()
    assert cap_res["max_whiteboards"] == 8

    # Reset back to 5
    admin.patch("/admin/settings/whiteboards", json={"max_whiteboards_per_scope": 5})


def test_board_index_boundary_validation(as_user, ids):
    """Board indices beyond the configured max or negative are rejected with 422."""
    bharat = as_user("bharat")
    ws_id = ids["workspaces"]["section_a"]

    # Exceeding configured max (default 5, so index 5 is out of bounds [0..4])
    r_patch = bharat.patch(f"/workspaces/{ws_id}/boards/5", json={"title": "Too Far"})
    assert r_patch.status_code == 422
    assert "invalid_board_index" in r_patch.json()["error"]["code"]

    r_get = bharat.get(f"/workspaces/{ws_id}/board?board_index=5")
    assert r_get.status_code == 422

    # Negative index rejected by pydantic or handler
    r_neg = bharat.patch(f"/workspaces/{ws_id}/boards/-1", json={"title": "Negative"})
    assert r_neg.status_code in (404, 422)
    assert bharat.get(f"/workspaces/{ws_id}/board?board_index=-1").status_code == 422
