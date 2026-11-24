"""Regression tests for the 24 November full review: limiter memory, password guessing, sockets."""

import pytest
from sqlalchemy import select

from labadda.config import load_settings
from labadda.models import AuditEvent
from labadda.security import RateLimiter
from tests.test_realtime import recv_until, ws_url


def test_rate_limiter_forgets_idle_keys_once_the_table_is_large():
    limiter = RateLimiter(sweep_at=50)
    for number in range(500):
        # A zero-second window makes every earlier key idle by the time the next one arrives.
        assert limiter.hit(f"login:made-up-{number}", 3, 0)
    assert len(limiter) <= 50


def test_rate_limiter_still_limits_a_busy_key_across_sweeps():
    limiter = RateLimiter(sweep_at=5)
    assert all(limiter.hit("login:asha", 3, 300) for _ in range(3))
    for number in range(20):
        limiter.hit(f"other-{number}", 3, 0)
    assert not limiter.hit("login:asha", 3, 300)


def test_auth_password_change_is_limited_and_audited(as_user, db_factory, settings):
    bharat = as_user("bharat")
    wrong = {"current_password": "not-the-password", "new_password": "new-fixture-pass-123"}
    codes = [
        bharat.post("/auth/password", json=wrong).status_code
        for _ in range(settings.login_attempts_per_window)
    ]
    assert set(codes) == {422}
    assert bharat.post("/auth/password", json=wrong).status_code == 429
    with db_factory() as db:
        denied = db.scalars(select(AuditEvent).where(AuditEvent.action == "auth.password_changed")).all()
    assert len(denied) == settings.login_attempts_per_window


def test_socket_answers_non_object_messages_and_stays_open(as_user, settings):
    with as_user("bharat").client.websocket_connect(ws_url(settings)) as conn:
        recv_until(conn, "hello")
        for raw in ("[]", "3", '"text"', "null"):
            conn.send_text(raw)
            assert recv_until(conn, "error")["code"] == "bad_message"
        conn.send_text('{"type": "ping"}')
        assert recv_until(conn, "pong")["type"] == "pong"


@pytest.mark.parametrize(
    "name",
    [
        "LABADDA_SESSION_IDLE_MINUTES",
        "LABADDA_SESSION_ABSOLUTE_HOURS",
        "LABADDA_REMINDER_INTERVAL_SECONDS",
        "LABADDA_PANEL_IDLE_SECONDS",
        "LABADDA_MAX_ATTACHMENT_BYTES",
        "LABADDA_BOARD_KEEP_REVISIONS",
    ],
)
@pytest.mark.parametrize("value", ["0", "-5"])
def test_counts_and_durations_must_be_positive(name, value):
    # Zero would sign everyone out at once, or spin the reminder loop against the database.
    with pytest.raises(ValueError, match=name):
        load_settings({name: value})
