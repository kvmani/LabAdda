"""A1 console gates preserve operational delegation and content isolation."""

import uuid
from datetime import timedelta

import pytest

from labadda import inventory_jobs, policy
from labadda.deps import require_console
from labadda.models import UsageReaderGrant
from labadda.security import utcnow
from tests.test_capabilities import grant
from tests.test_panel import PANEL, pair


def test_admin_and_reader_console_responses_exclude_content(as_user, ids, db_factory):
    member = as_user("ben")
    secrets = (
        "Synthetic private note title",
        "Synthetic private post body",
        "Synthetic private chat text",
        "synthetic-private-file.pdf",
    )
    workspace = ids["workspaces"]["section_a"]
    assert member.post("/notes", json={"title": secrets[0], "body": secrets[0]}).status_code == 201
    assert member.post(f"/workspaces/{workspace}/posts", json={"body": secrets[1]}).status_code == 201
    assert (
        member.post(
            f"/workspaces/{workspace}/chat", json={"body": secrets[2], "client_id": str(uuid.uuid4())}
        ).status_code
        == 201
    )
    assert (
        member.post(
            "/uploads", files={"file": (secrets[3], b"%PDF-1.4\nSynthetic\n%%EOF", "application/pdf")}
        ).status_code
        == 201
    )
    admin = as_user("admin")
    assert grant(admin, ids["users"]["ben"]).status_code == 201
    job = inventory_jobs.enqueue(db_factory, "synthetic-console-check", {})
    shared_paths = (
        "/admin/console",
        "/admin/usage",
        "/admin/usage-observations",
        "/admin/storage-inspections",
        "/admin/inventory-jobs",
        f"/admin/inventory-jobs/{job}",
    )
    admin_paths = (
        "/admin/users",
        "/admin/workspaces",
        "/admin/audit",
        "/admin/usage-readers",
        "/admin/policy-drafts",
        f"/admin/workspaces/{workspace}/memberships",
    )
    for client, paths in ((member, shared_paths), (admin, shared_paths + admin_paths)):
        for path in paths:
            response = client.get(path)
            assert response.status_code == 200, path
            for secret in secrets:
                assert secret not in response.text, path
    assert admin.get("/admin/console").json() == {
        "sections": list(policy.CONSOLE_SECTIONS),
        "read_only": False,
    }
    assert admin.get(f"/workspaces/{workspace}/posts").status_code == 404


@pytest.mark.parametrize("name", ["asha", "ben", "chen", "dana", "eli"])
def test_members_do_not_receive_console_authority(as_user, name):
    assert as_user(name).get("/admin/console").status_code == 403


def test_usage_reader_navigation_never_grants_administration(as_user, ids):
    admin = as_user("admin")
    reader = as_user("ben")
    assert grant(admin, ids["users"]["ben"]).status_code == 201
    assert reader.get("/admin/console").json() == {
        "sections": list(policy.READER_SECTIONS),
        "read_only": True,
    }
    for path in (
        "/admin/users",
        "/admin/workspaces",
        "/admin/audit",
        "/admin/usage-readers",
        "/admin/policy-drafts",
    ):
        assert reader.get(path).status_code == 403
    assert reader.get("/admin/usage").status_code == 200
    assert reader.post("/admin/usage-observations", json={}).status_code == 403


def test_expired_or_revoked_reader_loses_console(as_user, ids, db_factory):
    admin = as_user("admin")
    reader = as_user("ben")
    assert grant(admin, ids["users"]["ben"]).status_code == 201
    assert reader.get("/admin/console").status_code == 200
    with db_factory() as db:
        delegation = db.get(UsageReaderGrant, ids["users"]["ben"])
        delegation.expires_at = utcnow() - timedelta(seconds=1)
        db.commit()
    assert reader.get("/admin/console").status_code == 403
    assert reader.get("/admin/usage").status_code == 403


def test_signed_out_deactivated_and_panel_sessions_cannot_open_console(as_user, make_client, ids):
    client = make_client()
    assert client.get("/admin/console").status_code == 401
    assert client.login("fay").status_code == 401
    assert client.get("/admin/console").status_code == 401
    kiosk = pair(as_user, make_client, ids)
    assert kiosk.get("/admin/console").status_code == 401
    admin = as_user("admin")
    assert admin.get("/admin/console", headers=PANEL).status_code == 401
    assert admin.get("/admin/users", headers=PANEL).status_code == 401


def test_invalid_console_section_cannot_be_registered():
    with pytest.raises(ValueError, match="Unknown console section"):
        require_console("misspelled")


def test_explicit_panel_write_rejected_before_normal_csrf(as_user):
    admin = as_user("admin")
    response = admin.client.post(admin.url("/admin/users"), headers=PANEL, json={})
    assert response.status_code == 401
