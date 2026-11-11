"""T03 (in-process): prefixed and root instances, cookie scoping, health and readiness."""

from dataclasses import replace

from fastapi.testclient import TestClient
from labadda.app import create_app, expected_schema_head
from labadda.fixtures import fixture_password


def test_prefixed_instance_routes_and_cookie_path(settings, ids, tmp_path):
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text(
        "<!doctype html><html><head><title>LabAdda</title></head><body></body></html>"
    )
    (dist / "assets" / "app.js").write_text("console.log(1)")
    pre = create_app(
        replace(settings, base_path="/labadda-staging", cookie_name="labadda_staging", frontend_dist=dist)
    )
    root = create_app(replace(settings, base_path="", cookie_name="labadda_root", frontend_dist=dist))
    with TestClient(pre) as p, TestClient(root) as r:
        login = p.post(
            "/labadda-staging/api/v1/auth/login", json={"username": "ben", "password": fixture_password()}
        )
        assert login.status_code == 200
        cookie = login.headers["set-cookie"]
        assert "labadda_staging=" in cookie and "Path=/labadda-staging" in cookie
        assert p.get("/labadda-staging/api/v1/auth/session").status_code == 200
        assert p.get("/api/v1/auth/session").status_code == 404
        deep = p.get("/labadda-staging/w/123/chat")
        assert deep.status_code == 200 and '<base href="/labadda-staging/">' in deep.text
        assert '"base": "/labadda-staging"' in deep.text
        assert p.get("/labadda-staging", follow_redirects=False).headers["location"] == "/labadda-staging/"
        asset = p.get("/labadda-staging/assets/app.js")
        assert asset.status_code == 200 and "immutable" in asset.headers["cache-control"]
        assert p.get("/labadda-staging/assets/../index.html").status_code in (404, 200)
        assert p.get("/labadda-staging/api/v1/nope").status_code == 404
        assert p.get("/labadda-staging/healthz").json() == {"status": "ok"}
        assert p.get("/labadda-staging/readyz").json() == {"status": "ready"}
        # Root instance is independent.
        assert r.get("/api/v1/auth/session").status_code == 401
        r.post("/api/v1/auth/login", json={"username": "asha", "password": fixture_password()})
        assert r.get("/api/v1/auth/session").json()["user"]["username"] == "asha"
        p.post("/labadda-staging/api/v1/auth/logout", headers={"X-CSRF-Token": login.json()["csrf_token"]})
        assert r.get("/api/v1/auth/session").status_code == 200


def test_api_responses_not_cached(as_user):
    r = as_user("ben").get("/workspaces")
    assert "no-store" in r.headers["cache-control"]


def test_readiness_fails_on_schema_mismatch(settings, ids, db_factory):
    from sqlalchemy import text

    app = create_app(settings)
    with db_factory() as db:
        db.execute(text("update alembic_version set version_num = '0002'"))
        db.commit()
    try:
        with TestClient(app) as c:
            assert c.get(f"{settings.base_path}/readyz").status_code == 503
    finally:
        with db_factory() as db:
            db.execute(text("update alembic_version set version_num = :v"), {"v": expected_schema_head()})
            db.commit()


def test_fixture_command_refused_for_staging(monkeypatch, capsys):
    from labadda.cli import main

    monkeypatch.setenv("LABADDA_ENV", "staging")
    assert main(["seed"]) == 2
