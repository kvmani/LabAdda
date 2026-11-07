"""T02: session lifecycle, CSRF, expiry, origin, last-admin race, offboarding."""

import threading
from datetime import timedelta

from labadd.models import AuthSession
from labadd.security import utcnow


def test_login_session_logout(make_client):
    api = make_client()
    assert api.get("/auth/session").status_code == 401
    r = api.login("ben")
    assert r.status_code == 200 and r.json()["user"]["username"] == "ben"
    assert "httponly" in r.headers["set-cookie"].lower()
    assert "samesite=strict" in r.headers["set-cookie"].lower()
    assert api.get("/auth/session").status_code == 200
    assert api.post("/auth/logout").status_code == 200
    assert api.get("/auth/session").status_code == 401


def test_wrong_password_generic_error(make_client):
    a = make_client().login("ben", "wrong-password")
    b = make_client().login("nobody", "wrong-password")
    assert a.status_code == b.status_code == 401
    assert a.json() == b.json()


def test_csrf_required_for_unsafe_requests(as_user, ids):
    ben = as_user("ben")
    ws = ids["workspaces"]["section_a"]
    r = ben.client.post(ben.url(f"/workspaces/{ws}/posts"), json={"body": "no token"})
    assert r.status_code == 403 and r.json()["error"]["code"] == "csrf_failed"
    r = ben.client.post(ben.url(f"/workspaces/{ws}/posts"), json={"body": "bad"}, headers={"X-CSRF-Token": "x"})
    assert r.status_code == 403


def test_untrusted_origin_rejected(as_user, ids):
    ben = as_user("ben")
    r = ben.post(f"/workspaces/{ids['workspaces']['section_a']}/posts", json={"body": "x"},
                 headers={"Origin": "http://evil.example"})
    assert r.status_code == 403 and r.json()["error"]["code"] == "bad_origin"
    r = ben.post(f"/workspaces/{ids['workspaces']['section_a']}/posts", json={"body": "ok"},
                 headers={"Origin": "http://testserver"})
    assert r.status_code == 201


def test_idle_and_absolute_expiry(as_user, db_factory):
    ben = as_user("ben")
    with db_factory() as db:
        for s in db.query(AuthSession).all():
            s.last_seen_at = utcnow() - timedelta(hours=5)
        db.commit()
    assert ben.get("/auth/session").status_code == 401
    asha = as_user("asha")
    with db_factory() as db:
        for s in db.query(AuthSession).all():
            s.expires_at = utcnow() - timedelta(seconds=1)
        db.commit()
    assert asha.get("/auth/session").status_code == 401


def test_deactivation_revokes_sessions_and_keeps_attribution(as_user, ids):
    ben = as_user("ben")
    ws = ids["workspaces"]["section_a"]
    post = ben.post(f"/workspaces/{ws}/posts", json={"body": "Before I leave"}).json()
    admin = as_user("admin")
    assert admin.patch(f"/admin/users/{ids['users']['ben']}", json={"is_active": False}).status_code == 200
    assert ben.get("/auth/session").status_code == 401
    feed = as_user("asha").get(f"/workspaces/{ws}/posts").json()
    assert feed["posts"][0]["id"] == post["id"]
    assert feed["posts"][0]["author"]["username"] == "ben"
    assert feed["posts"][0]["author"]["is_active"] is False


def test_activation_flow_and_single_use(as_user, make_client):
    admin = as_user("admin")
    r = admin.post("/admin/users", json={"username": "gita", "display_name": "Gita Sen"})
    assert r.status_code == 201
    token = r.json()["activation_token"]
    newbie = make_client()
    assert newbie.login("gita", "anything-at-all").status_code == 401
    assert newbie.client.post(newbie.url("/auth/activate"), json={"token": token, "password": "short"}).status_code == 422
    ok = newbie.client.post(newbie.url("/auth/activate"), json={"token": token, "password": "a-long-password"})
    assert ok.status_code == 200
    again = make_client().client.post(newbie.url("/auth/activate"), json={"token": token, "password": "another-password"})
    assert again.status_code == 422
    assert make_client().login("gita", "a-long-password").status_code == 200


def test_reset_revokes_sessions(as_user, ids):
    ben = as_user("ben")
    r = as_user("admin").post(f"/admin/users/{ids['users']['ben']}/reset")
    assert r.status_code == 200 and r.json()["reset_token"]
    assert ben.get("/auth/session").status_code == 401


def test_last_admin_protected(as_user, ids):
    admin = as_user("admin")
    r = admin.patch(f"/admin/users/{ids['users']['admin']}", json={"is_admin": False})
    assert r.status_code == 409 and r.json()["error"]["code"] == "last_admin"
    r = admin.patch(f"/admin/users/{ids['users']['admin']}", json={"is_active": False})
    assert r.status_code == 409


def test_last_admin_race(as_user, ids, make_client):
    admin = as_user("admin")
    assert admin.patch(f"/admin/users/{ids['users']['dana']}", json={"is_admin": True}).status_code == 200
    dana = make_client("dana")
    results = []
    barrier = threading.Barrier(2)

    def demote(api, target):
        barrier.wait()
        results.append(api.patch(f"/admin/users/{target}", json={"is_admin": False}).status_code)

    threads = [threading.Thread(target=demote, args=(admin, ids["users"]["dana"])),
               threading.Thread(target=demote, args=(dana, ids["users"]["admin"]))]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert sorted(results) in ([200, 409], [200, 401], [200, 403])
    users = admin.get("/admin/users")
    if users.status_code == 200:
        active_admins = [u for u in users.json()["users"] if u["is_admin"] and u["is_active"]]
    else:
        active_admins = [u for u in dana.get("/admin/users").json()["users"] if u["is_admin"] and u["is_active"]]
    assert len(active_admins) == 1


def test_login_rate_limit(make_client):
    api = make_client()
    codes = [api.login("ben", "wrong-password").status_code for _ in range(12)]
    assert codes[-1] == 429


def test_admin_actions_are_audited(as_user, ids):
    admin = as_user("admin")
    admin.put(f"/admin/workspaces/{ids['workspaces']['section_b']}/memberships",
              json={"user_id": ids["users"]["ben"], "reason": "temporary help"})
    events = admin.get("/admin/audit").json()["events"]
    assert any(e["action"] == "membership.set" and e["reason"] == "temporary help" for e in events)
    assert all("password" not in str(e["detail"]) for e in events)
