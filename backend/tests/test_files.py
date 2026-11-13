"""T06: validated attachments, protected downloads, quotas and cleanup."""

import io
from datetime import timedelta

from PIL import Image

from labadda.api.files import cleanup_provisional
from labadda.models import Asset
from labadda.security import utcnow


def png_bytes(trailer: bytes = b"") -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (40, 30), (200, 10, 10)).save(buf, format="PNG")
    return buf.getvalue() + trailer


PDF = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"


def upload(api, name, data, ctype):
    return api.post("/uploads", files={"file": (name, data, ctype)})


def test_upload_attach_download_and_scope(as_user, ids):
    bharat = as_user("bharat")
    a = upload(bharat, "../../etc/passwd.pdf", PDF, "application/pdf").json()
    assert a["display_name"] == "passwd.pdf" and a["status"] == "provisional"
    # Provisional uploads are private to the uploader.
    assert as_user("asha").get(f"/files/{a['id']}").status_code == 404
    img = upload(bharat, "plot.png", png_bytes(b"<script>alert(1)</script>"), "image/png").json()
    ws = ids["workspaces"]["section_a"]
    post = bharat.post(
        f"/workspaces/{ws}/posts", json={"body": "Data", "attachment_ids": [a["id"], img["id"]]}
    )
    assert post.status_code == 201 and len(post.json()["attachments"]) == 2
    r = as_user("asha").get(f"/files/{a['id']}")
    assert r.status_code == 200 and r.headers["content-disposition"].startswith("attachment")
    assert r.headers["x-content-type-options"] == "nosniff" and "no-store" in r.headers["cache-control"]
    prev = as_user("asha").get(f"/files/{img['id']}/preview")
    assert prev.status_code == 200 and b"<script>" not in prev.content
    for user in ("chitra", "admin", "esha"):
        assert as_user(user).get(f"/files/{a['id']}").status_code == 404
        assert as_user(user).get(f"/files/{img['id']}/preview").status_code == 404
    # Asset cannot be reused on another post.
    again = bharat.post(f"/workspaces/{ws}/posts", json={"body": "again", "attachment_ids": [a["id"]]})
    assert again.status_code == 422
    # Deleting the post hides the file.
    bharat.delete(f"/posts/{post.json()['id']}")
    assert as_user("asha").get(f"/files/{a['id']}").status_code == 404


def test_rejects_forged_and_unsupported(as_user):
    bharat = as_user("bharat")
    assert upload(bharat, "x.pdf", b"<html><script>1</script></html>", "application/pdf").status_code == 422
    assert upload(bharat, "x.png", PDF, "image/png").json()["error"]["code"] == "type_mismatch"
    assert upload(bharat, "x.svg", b"<svg onload=alert(1)>", "image/svg+xml").status_code == 422
    assert (
        upload(bharat, "x.png", b"\x89PNG\r\n\x1a\nnot really", "image/png").json()["error"]["code"]
        == "invalid_image"
    )
    assert upload(bharat, "empty.pdf", b"", "application/pdf").status_code == 422


def test_size_limit_and_quota(as_user, app):
    from dataclasses import replace

    app.state.settings = replace(
        app.state.settings, max_attachment_bytes=1000, user_quota_bytes=len(PDF) + 10
    )
    bharat = as_user("bharat")
    assert (
        upload(bharat, "big.pdf", PDF + b"0" * 2000, "application/pdf").json()["error"]["code"]
        == "file_too_large"
    )
    assert upload(bharat, "a.pdf", PDF, "application/pdf").status_code == 201
    assert upload(bharat, "b.pdf", PDF, "application/pdf").json()["error"]["code"] == "quota_exceeded"


def test_attachment_count_limit(as_user, ids):
    bharat = as_user("bharat")
    assets = [upload(bharat, f"f{i}.pdf", PDF, "application/pdf").json()["id"] for i in range(6)]
    r = bharat.post(
        f"/workspaces/{ids['workspaces']['section_a']}/posts", json={"body": "x", "attachment_ids": assets}
    )
    assert r.status_code == 422 and r.json()["error"]["code"] == "too_many_attachments"


def test_cleanup_removes_only_stale_provisional(as_user, ids, app, db_factory):
    bharat = as_user("bharat")
    stale = upload(bharat, "stale.pdf", PDF, "application/pdf").json()
    kept = upload(bharat, "kept.pdf", PDF, "application/pdf").json()
    bharat.post(
        f"/workspaces/{ids['workspaces']['section_a']}/posts",
        json={"body": "x", "attachment_ids": [kept["id"]]},
    )
    with db_factory() as db:
        for a in db.query(Asset).all():
            a.created_at = utcnow() - timedelta(days=2)
        db.commit()
        assert cleanup_provisional(db, app.state.assets, app.state.settings) == 1
    assert bharat.get(f"/files/{stale['id']}").status_code == 404
    assert bharat.get(f"/files/{kept['id']}").status_code == 200


def test_discard_own_provisional_only(as_user):
    bharat = as_user("bharat")
    a = upload(bharat, "d.pdf", PDF, "application/pdf").json()
    assert as_user("asha").delete(f"/uploads/{a['id']}").status_code == 404
    assert bharat.delete(f"/uploads/{a['id']}").status_code == 200
