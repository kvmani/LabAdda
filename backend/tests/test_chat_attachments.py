"""C4 validated file destinations and private chat delivery/accounting."""

import uuid
from io import BytesIO

import pytest
from PIL import Image
from sqlalchemy import delete, select

from labadda.cli import alembic_config
from labadda.models import Asset, ChatMessage, Membership
from labadda.workspace_usage import workspace_observation
from tests.migration_helpers import downgrade_legacy


def upload(api, png=False):
    if png:
        data = BytesIO()
        Image.new("RGB", (12, 12), "green").save(data, format="PNG")
        data = data.getvalue()
        name = "fixture.png"
        mime = "image/png"
    else:
        data = b"%PDF-1.4\nSynthetic handoff\n%%EOF"
        name = "handoff.pdf"
        mime = "application/pdf"
    result = api.post("/uploads", files={"file": (name, data, mime)})
    assert result.status_code == 201, result.text
    return result.json(), data


@pytest.mark.parametrize(
    "scope,reader,outsider", [("section_a", "asha", "chen"), ("reading_club", "chen", "dana")]
)
def test_chat_attachment_retry_delivery_and_accounting(as_user, ids, db_factory, scope, *, reader, outsider):
    api = as_user("ben")
    ws = ids["workspaces"][scope]
    asset, data = upload(api)
    body = {"client_id": str(uuid.uuid4()), "body": "Reviewed handoff", "attachment_ids": [asset["id"]]}
    url = f"/workspaces/{ws}/chat"
    created = api.post(url, json=body)
    assert created.status_code == 201, created.text
    row = created.json()
    assert row["attachments"][0]["id"] == asset["id"]
    assert api.post(url, json=body).json()["id"] == row["id"]
    assert api.post(url, json={**body, "attachment_ids": []}).status_code == 409
    assert api.post(url, json={**body, "client_id": str(uuid.uuid4())}).status_code == 422
    assert as_user(reader).get("/files/" + asset["id"]).content == data
    for name in [outsider, "admin"]:
        assert as_user(name).get("/files/" + asset["id"]).status_code == 404
    assert api.get("/files/" + asset["id"], headers={"X-LabAdda-Panel": "1"}).status_code == 401
    with db_factory() as db:
        observation = workspace_observation(db, uuid.UUID(ws))
        assert observation["files"]["retained_files"] == 1 and observation["files"][
            "retained_original_bytes"
        ] == len(data)
        db.execute(
            delete(Membership).where(
                Membership.user_id == ids["users"][reader], Membership.workspace_id == ws
            )
        )
        db.commit()
    assert as_user(reader).get("/files/" + asset["id"]).status_code == 404


def test_reply_image_preview_and_attachment_only_message(as_user, ids):
    api = as_user("ben")
    ws = ids["workspaces"]["section_a"]
    url = f"/workspaces/{ws}/chat"
    root = api.post(url, json={"body": "Root", "client_id": str(uuid.uuid4())}).json()
    asset, _ = upload(api, True)
    reply = api.post(
        url, json={"client_id": str(uuid.uuid4()), "parent_id": root["id"], "attachment_ids": [asset["id"]]}
    )
    assert reply.status_code == 201, reply.text
    assert as_user("asha").get("/files/" + asset["id"] + "/preview").status_code == 200
    assert as_user("chen").get("/files/" + asset["id"] + "/preview").status_code == 404
    assert (
        api.get(url + "/" + root["id"] + "/replies").json()["messages"][0]["attachments"][0]["id"]
        == asset["id"]
    )
    assert api.post(url, json={"body": "", "client_id": str(uuid.uuid4())}).status_code == 422


def test_other_owner_and_cross_destination_reuse_are_denied(as_user, ids):
    api = as_user("ben")
    asset, _ = upload(as_user("asha"))
    ws = ids["workspaces"]["section_a"]
    payload = {"body": "Foreign file", "client_id": str(uuid.uuid4()), "attachment_ids": [asset["id"]]}
    assert api.post(f"/workspaces/{ws}/chat", json=payload).status_code == 422
    assert (
        as_user("asha")
        .post(f"/workspaces/{ws}/posts", json={"body": "Already bound", "attachment_ids": [asset["id"]]})
        .status_code
        == 201
    )
    assert as_user("asha").post(f"/workspaces/{ws}/chat", json=payload).status_code == 422
    assert api.post("/uploads", files={"file": ("unsafe.svg", b"<svg/>", "image/svg+xml")}).status_code == 422


def test_file_binding_rolls_back_with_expired_identity(as_user, ids, db_factory, monkeypatch):
    from labadda import identity_locks
    from labadda.api import chat

    api = as_user("ben")
    asset, _ = upload(api)
    original = chat._mark_read

    def expire(*args):
        original(*args)
        monkeypatch.setattr(identity_locks, "session_valid", lambda *_: False)

    monkeypatch.setattr(chat, "_mark_read", expire)
    result = api.post(
        f"/workspaces/{ids['workspaces']['section_a']}/chat",
        json={"body": "Must not bind", "client_id": str(uuid.uuid4()), "attachment_ids": [asset["id"]]},
    )
    assert result.status_code == 401
    with db_factory() as db:
        row = db.get(Asset, asset["id"])
        assert row.status == "provisional" and row.chat_message_id is None
        assert db.scalar(select(ChatMessage)) is None


def test_attachment_binding_blocks_lossy_downgrade(as_user, ids, settings):
    api = as_user("ben")
    asset, _ = upload(api)
    assert (
        api.post(
            f"/workspaces/{ids['workspaces']['section_a']}/chat",
            json={"body": "Kept file", "client_id": str(uuid.uuid4()), "attachment_ids": [asset["id"]]},
        ).status_code
        == 201
    )
    with pytest.raises(Exception, match="Chat attachments exist"):
        downgrade_legacy(alembic_config(settings.database_url), "0023")
