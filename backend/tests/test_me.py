"""P8: own profile, password change and session list, with the denial matrix."""

import pytest

from labadda.fixtures import fixture_password
from labadda.models import AuditEvent, AuthSession
from tests.test_panel import PANEL, pair
from tests.test_realtime import recv_until, ws_url

UA_FIREFOX = "Mozilla/5.0 (X11; Linux x86_64; rv:128.0) Gecko/20100101 Firefox/128.0"
UA_EDGE = "Mozilla/5.0 (Windows NT 10.0) AppleWebKit/537.36 Chrome/126.0 Safari/537.36 Edg/126.0"
NEW_PASSWORD = "a-brand-new-passphrase"


def sign_in(make_client, username="ben", agent=UA_FIREFOX):
    api = make_client()
    r = api.client.post(
        api.url("/auth/login"),
        json={"username": username, "password": fixture_password()},
        headers={"User-Agent": agent},
    )
    assert r.status_code == 200
    api.csrf = r.json()["csrf_token"]
    return api


def change(api, current=None, new=NEW_PASSWORD):
    return api.post(
        "/me/password", json={"current_password": current or fixture_password(), "new_password": new}
    )


def test_profile_shows_own_record_and_access(as_user, ids):
    body = as_user("ben").get("/me/profile").json()
    assert body["record"]["username"] == "ben"
    assert body["record"]["display_name"] == "Ben Okafor"
    names = {m["workspace"]["name"] for m in body["access"]}
    assert "Thin Films Section" in names
    assert any(not m["inherited"] for m in body["access"])


def test_denial_matrix(make_client, as_user, ids):
    anon = make_client()
    assert anon.get("/me/profile").status_code == 401
    assert anon.get("/me/sessions").status_code == 401
    assert anon.delete(f"/me/sessions/{ids['users']['ben']}").status_code == 401
    kiosk = pair(as_user, make_client, ids)
    assert kiosk.get("/me/profile").status_code == 401
    assert kiosk.get("/me/sessions").status_code == 401
    assert kiosk.post("/me/password", json={"current_password": "x", "new_password": "y"}).status_code == 401
    # A desktop cookie with the panel marker is refused too.
    assert as_user("ben").get("/me/profile", headers=PANEL).status_code == 401


def test_deactivated_user_cannot_use_endpoints(as_user, make_client):
    ben = as_user("ben")
    assert as_user("admin").patch(f"/admin/users/{_id(ben)}", json={"is_active": False}).status_code == 200
    assert ben.get("/me/profile").status_code == 401


def _id(api):
    return api.get("/auth/session").json()["user"]["id"]


def test_sessions_list_has_label_and_no_tokens(make_client):
    desk = sign_in(make_client)
    sign_in(make_client, agent=UA_EDGE)
    items = desk.get("/me/sessions").json()["items"]
    assert items[0]["browser"] == "Firefox on Linux"
    assert items[0]["current"] is True and items[1]["current"] is False
    assert items[1]["browser"] == "Edge on Windows"
    text = desk.get("/me/sessions").text + desk.get("/me/profile").text
    cookie = desk.client.cookies.get("labadda_session") or next(iter(desk.client.cookies.values()))
    assert cookie not in text and desk.csrf not in text


def test_end_other_session_immediately(make_client, settings):
    first = sign_in(make_client)
    second = sign_in(make_client, agent=UA_EDGE)
    other = next(i for i in first.get("/me/sessions").json()["items"] if not i["current"])
    with second.client.websocket_connect(ws_url(settings)) as conn:
        conn.receive_json()
        assert first.delete(f"/me/sessions/{other['id']}").status_code == 200
        assert recv_until(conn, "session_ended")
    assert second.get("/auth/session").status_code == 401
    assert first.get("/auth/session").status_code == 200
    assert len(first.get("/me/sessions").json()["items"]) == 1


def test_cannot_end_current_or_foreign_session(make_client, db_factory):
    ben = sign_in(make_client)
    chen = sign_in(make_client, "chen")
    mine = ben.get("/me/sessions").json()["items"][0]
    assert ben.delete(f"/me/sessions/{mine['id']}").json()["error"]["code"] == "current_session"
    theirs = chen.get("/me/sessions").json()["items"][0]
    assert ben.delete(f"/me/sessions/{theirs['id']}").status_code == 404
    assert ben.delete("/me/sessions/00000000-0000-0000-0000-000000000000").status_code == 404
    assert chen.get("/auth/session").status_code == 200
    with db_factory() as db:
        assert db.query(AuthSession).filter(AuthSession.revoked_at.is_not(None)).count() == 0


def test_password_change_ends_other_sessions_only(make_client, settings, db_factory):
    keep = sign_in(make_client)
    other = sign_in(make_client, agent=UA_EDGE)
    with other.client.websocket_connect(ws_url(settings)) as conn:
        conn.receive_json()
        r = change(keep)
        assert r.status_code == 200 and r.json() == {"ok": True, "sessions_ended": 1}
        assert recv_until(conn, "session_ended")
    assert keep.get("/me/profile").status_code == 200
    assert other.get("/me/profile").status_code == 401
    assert make_client().login("ben").status_code == 401
    assert make_client().login("ben", NEW_PASSWORD).status_code == 200
    assert "token" not in r.text and NEW_PASSWORD not in r.text
    with db_factory() as db:
        events = db.query(AuditEvent).filter_by(action="auth.password_changed").all()
        assert len(events) == 1 and NEW_PASSWORD not in str(events[0].detail)


def test_password_rules(as_user):
    ben = as_user("ben")
    assert change(ben, new="short").json()["error"]["code"] == "weak_password"
    assert change(ben, new=fixture_password()).json()["error"]["code"] == "password_unchanged"
    assert ben.post("/me/password", json={"current_password": "x"}).status_code == 422
    assert (
        ben.post("/me/password", json={"current_password": "x", "new_password": "y" * 12, "z": 1}).status_code
        == 422
    )


def test_wrong_current_password_audited_and_rate_limited(as_user, settings, db_factory):
    ben = as_user("ben")
    for _ in range(settings.login_attempts_per_window):
        assert change(ben, current="not-my-password").json()["error"]["code"] == "invalid_credentials"
    assert change(ben, current="not-my-password").status_code == 429
    assert change(ben).status_code == 429
    with db_factory() as db:
        denied = db.query(AuditEvent).filter_by(action="auth.password_changed", outcome="denied").count()
    assert denied == settings.login_attempts_per_window
    assert as_user("chen").get("/me/profile").status_code == 200


def test_requires_csrf(as_user):
    ben = as_user("ben")
    r = ben.client.post(
        ben.url("/me/password"), json={"current_password": fixture_password(), "new_password": NEW_PASSWORD}
    )
    assert r.status_code == 403


@pytest.mark.parametrize(
    ("agent", "label"),
    [
        (None, None),
        ("curl/8.0", "Other browser"),
        (UA_FIREFOX, "Firefox on Linux"),
        (UA_EDGE, "Edge on Windows"),
    ],
)
def test_agent_label(agent, label):
    from labadda.security import agent_label

    assert agent_label(agent) == label
