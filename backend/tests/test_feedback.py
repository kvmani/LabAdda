"""Pilot: the Feedback button. Server-filled facts, attachments, admin triage, access denials."""

import io
import smtplib
import uuid
from datetime import timedelta

import pytest
from alembic import command
from PIL import Image
from sqlalchemy import text

from labadda import build_info, feedback_mail
from labadda import feedback as fb
from labadda.cli import alembic_config
from labadda.models import Asset, AuditEvent, Feedback, FeedbackMail, User
from labadda.security import feedback_limiter, utcnow
from tests.conftest import recreate_schema
from tests.test_capabilities import grant
from tests.test_panel import PANEL, pair

PDF = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"
SECRET = "Kalpana Rao's pressure sensor drifts after 3 pm"


def png(width=40) -> bytes:
    out = io.BytesIO()
    Image.new("RGB", (width, 30), (10, 120, 200)).save(out, format="PNG")
    return out.getvalue()


def webp() -> bytes:
    out = io.BytesIO()
    Image.new("RGB", (20, 20), (200, 10, 10)).save(out, format="WEBP")
    return out.getvalue()


def send(api, *, files=(), message=SECRET, category="problem", client_id=None, **extra):
    data = {
        "client_id": client_id or uuid.uuid4().hex,
        "category": category,
        "message": message,
        "route": "/w/thin-films/board",
        "screen": "1920x1080",
        **extra,
    }
    upload = [("files", (name, body, ctype)) for name, body, ctype in files]
    return api.post("/feedback", data=data, files=upload or None)


def test_metadata_is_filled_by_the_server(as_user, db_factory, monkeypatch):
    monkeypatch.setattr(build_info, "commit_and_date", lambda: ("abc1234", "2026-11-13"))
    r = send(
        as_user("bharat"),
        software_version="9.9.9",
        commit="forged",
        username="admin",
        created_at="2001-01-01T00:00:00Z",
    )
    assert r.status_code == 201 and set(r.json()) == {"id", "created_at"}
    with db_factory() as db:
        row = db.get(Feedback, uuid.UUID(r.json()["id"]))
        assert row.username == "bharat" and row.commit == "abc1234"
        assert row.software_version != "9.9.9" and row.created_at.year > 2020
        assert row.route == "/w/thin-films/board" and row.screen == "1920x1080" and row.status == "new"
        assert db.get(FeedbackMail, row.id).status == "queued"
        audit = db.query(AuditEvent).filter_by(action="feedback.submit").one()
        assert SECRET not in str(audit.detail) and audit.target_id == str(row.id)


def test_route_and_screen_are_validated(as_user, db_factory):
    api = as_user("bharat")
    ids_ = [
        send(api, route="/chat?token=abc#frag", screen="big").json()["id"],
        send(api, route="javascript:alert(1)", screen="10x10;drop").json()["id"],
    ]
    with db_factory() as db:
        first, second = (db.get(Feedback, uuid.UUID(i)) for i in ids_)
        assert (first.route, first.screen) == ("/chat", None)
        assert (second.route, second.screen) == (None, None)


def test_message_rules(as_user):
    api = as_user("bharat")
    assert send(api, message="   ").json()["error"]["code"] == "empty_message"
    assert send(api, message="x" * 5001).json()["error"]["code"] == "message_too_long"
    assert send(api, message="bad \x00 byte").json()["error"]["code"] == "invalid_message"
    assert send(api, category="rant").json()["error"]["code"] == "invalid_category"
    assert send(api, client_id="short").json()["error"]["code"] == "invalid_request_id"


def test_retry_with_the_same_request_id_is_idempotent(as_user, db_factory):
    api = as_user("bharat")
    first = send(api, client_id="retry-key-0001").json()
    assert send(api, client_id="retry-key-0001").json()["id"] == first["id"]
    assert send(api, client_id="retry-key-0001", message="different").status_code == 409
    with db_factory() as db:
        assert db.query(Feedback).count() == 1


def test_attachment_types_are_sniffed_not_trusted(as_user):
    api = as_user("bharat")
    ok = send(
        api,
        files=[
            ("a.png", png(), "image/png"),
            ("b.webp", webp(), "image/webp"),
            ("c.pdf", PDF, "application/pdf"),
            ("d.txt", b"line one\nline two\n", "text/plain"),
            ("e.jpg", png(), "application/octet-stream"),
        ],
    )
    assert ok.status_code == 201, ok.text
    bad = [
        ("x.png", b"<html><script>1</script></html>", "image/png"),
        ("x.svg", b"<svg onload=alert(1)>", "image/svg+xml"),
        ("x.png", PDF, "image/png"),
        ("x.txt", png(), "text/plain"),
        ("x.txt", b"binary\x00\x01data", "text/plain"),
        ("x.exe", b"MZ\x90\x00", "application/octet-stream"),
    ]
    for name, body, ctype in bad:
        assert send(api, files=[(name, body, ctype)]).status_code == 422, name


def test_attachment_count_and_size_caps(as_user, monkeypatch):
    api = as_user("bharat")
    too_many = [(f"{i}.txt", b"hello", "text/plain") for i in range(6)]
    assert send(api, files=too_many).json()["error"]["code"] == "too_many_attachments"
    assert send(api, files=[("e.txt", b"", "text/plain")]).json()["error"]["code"] == "empty_file"
    monkeypatch.setattr(fb, "MAX_FILE_BYTES", 100)
    monkeypatch.setattr(fb, "MAX_TOTAL_BYTES", 150)
    assert (
        send(api, files=[("big.txt", b"a" * 101, "text/plain")]).json()["error"]["code"] == "file_too_large"
    )
    pair_of = [("a.txt", b"a" * 90, "text/plain"), ("b.txt", b"b" * 90, "text/plain")]
    assert send(api, files=pair_of).json()["error"]["code"] == "files_too_large"


def test_quota_counts_feedback_files(as_user, settings, app, db_factory):
    api = as_user("bharat")
    app.state.settings = type(settings)(**{**settings.__dict__, "user_quota_bytes": 100})
    r = send(api, files=[("a.txt", b"a" * 200, "text/plain")])
    assert r.status_code == 422 and r.json()["error"]["code"] == "quota_exceeded"
    with db_factory() as db:
        assert db.query(Feedback).count() == 0 and db.query(Asset).count() == 0


def test_rate_limit_per_user(as_user):
    api = as_user("bharat")
    for _ in range(fb.SENDS_PER_HOUR):
        assert send(api).status_code == 201
    limited = send(api)
    assert limited.status_code == 429 and limited.json()["error"]["code"] == "feedback_rate_limited"
    assert send(as_user("asha")).status_code == 201
    feedback_limiter.reset()


def test_denials_for_senders(as_user, make_client, ids, db_factory):
    assert send(make_client()).status_code == 401
    kiosk = pair(as_user, make_client, ids)
    r = kiosk.api.client.post(
        kiosk.api.url("/feedback"),
        data={"client_id": "panel-client-01", "category": "problem", "message": "hi"},
        headers={**PANEL, "X-CSRF-Token": kiosk.csrf},
    )
    assert r.status_code == 401
    # A normal cookie plus the panel header is still refused: a board screen is never a person.
    stray = as_user("bharat")
    r = stray.post(
        "/feedback",
        data={"client_id": "panel-client-02", "category": "problem", "message": "hi"},
        headers=PANEL,
    )
    assert r.status_code == 401
    with db_factory() as db:
        db.get(User, ids["users"]["esha"]).is_active = False
        db.commit()
    assert send(as_user("asha")).status_code == 201


def test_deactivated_sender_is_refused(as_user, ids, db_factory):
    api = as_user("chitra")
    with db_factory() as db:
        db.get(User, ids["users"]["chitra"]).is_active = False
        db.commit()
    assert send(api).status_code in (401, 403)


def test_admin_list_and_detail(as_user, db_factory):
    send(as_user("bharat"), files=[("shot.png", png(), "image/png")], category="problem")
    send(as_user("asha"), category="suggestion", message="Please add dark mode")
    admin = as_user("admin")
    listing = admin.get("/admin/feedback").json()
    assert [i["username"] for i in listing["items"]] == ["asha", "bharat"]
    assert listing["items"][1]["attachment_count"] == 1
    assert listing["email"] == {"configured": False, "queued": 2, "failed": 0}
    assert SECRET not in str(listing) and "dark mode" not in str(listing)
    only = admin.get("/admin/feedback?category=problem&status=new").json()["items"]
    assert [i["username"] for i in only] == ["bharat"]
    assert admin.get("/admin/feedback?username=asha").json()["items"][0]["category"] == "suggestion"
    detail = admin.get(f"/admin/feedback/{only[0]['id']}").json()
    assert detail["message"] == SECRET and detail["username"] == "bharat"
    assert detail["software_version"] and detail["commit"] and detail["revision"] == 1
    assert detail["email"]["status"] == "queued" and detail["email"]["waiting_for_setup"] is True
    with db_factory() as db:
        assert db.query(AuditEvent).filter_by(action="feedback.read").count() == 1


def test_cursor_paging(as_user):
    api = as_user("bharat")
    for n in range(5):
        send(api, message=f"note {n}")
    admin = as_user("admin")
    first = admin.get("/admin/feedback?limit=2").json()
    second = admin.get(f"/admin/feedback?limit=2&cursor={first['next_cursor']}").json()
    third = admin.get(f"/admin/feedback?limit=2&cursor={second['next_cursor']}").json()
    seen = [i["id"] for page in (first, second, third) for i in page["items"]]
    assert len(seen) == len(set(seen)) == 5 and third["next_cursor"] is None
    assert admin.get("/admin/feedback?cursor=garbage").status_code == 422


def test_triage_uses_the_expected_revision_and_is_audited(as_user, db_factory):
    fid = send(as_user("bharat")).json()["id"]
    admin = as_user("admin")
    done = admin.patch(
        f"/admin/feedback/{fid}",
        json={"expected_revision": 1, "status": "resolved", "admin_note": "Re-zeroed."},
    )
    assert done.status_code == 200 and done.json()["status"] == "resolved" and done.json()["revision"] == 2
    stale = admin.patch(f"/admin/feedback/{fid}", json={"expected_revision": 1, "status": "seen"})
    assert stale.status_code == 409 and stale.json()["error"]["code"] == "feedback_changed"
    assert (
        admin.patch(f"/admin/feedback/{fid}", json={"expected_revision": 2, "status": "bogus"}).status_code
        == 422
    )
    assert (
        admin.patch(f"/admin/feedback/{fid}", json={"expected_revision": 2, "owner": "x"}).status_code == 422
    )
    with db_factory() as db:
        event = db.query(AuditEvent).filter_by(action="feedback.update").one()
        assert event.detail["before"] == "new" and event.detail["after"] == "resolved"
        assert "Re-zeroed" not in str(event.detail)


def test_attachments_download_only_for_administrators(as_user, make_client):
    fid = send(
        as_user("bharat"),
        files=[("shot.png", png(), "image/png"), ("log.txt", b"trace line\n", "text/plain")],
    ).json()["id"]
    admin = as_user("admin")
    files = admin.get(f"/admin/feedback/{fid}").json()["attachments"]
    image, text = files
    got = admin.get(image["url"].removeprefix("/api/v1"))
    assert got.status_code == 200 and got.headers["content-type"] == "image/png"
    assert got.headers["x-content-type-options"] == "nosniff" and "no-store" in got.headers["cache-control"]
    preview = admin.get(image["preview_url"].removeprefix("/api/v1"))
    assert preview.status_code == 200
    log = admin.get(text["url"].removeprefix("/api/v1"))
    assert log.headers["content-disposition"].startswith("attachment") and log.content == b"trace line\n"
    assert (
        admin.get(
            text["preview_url"] or f"/admin/feedback/{fid}/attachments/{text['id']}/preview"
        ).status_code
        == 404
    )
    # Not the sender, not a member, not the generic file route, not signed out.
    for who in ("bharat", "asha", "chitra"):
        assert as_user(who).get(image["url"].removeprefix("/api/v1")).status_code == 403
        assert as_user(who).get(f"/files/{image['id']}").status_code == 404
    assert make_client().get(image["url"].removeprefix("/api/v1")).status_code == 401
    other = uuid.uuid4()
    assert admin.get(f"/admin/feedback/{fid}/attachments/{other}").status_code == 404


def test_console_denials(as_user, make_client, ids):
    fid = send(as_user("bharat")).json()["id"]
    paths = ["/admin/feedback", f"/admin/feedback/{fid}"]
    for who in ("bharat", "asha", "chitra", "esha"):
        for path in paths:
            assert as_user(who).get(path).status_code == 403
        assert as_user(who).patch(f"/admin/feedback/{fid}", json={"expected_revision": 1}).status_code == 403
        assert as_user(who).post(f"/admin/feedback/{fid}/resend").status_code == 403
    for path in paths:
        assert make_client().get(path).status_code == 401
    assert grant(as_user("admin"), ids["users"]["deepa"]).status_code == 201
    reader = as_user("deepa")
    assert "feedback" not in reader.get("/admin/console").json()["sections"]
    for path in paths:
        assert reader.get(path).status_code == 403
    assert "feedback" in as_user("admin").get("/admin/console").json()["sections"]
    assert as_user("admin").get(f"/admin/feedback/{uuid.uuid4()}").status_code == 404


def test_panel_cannot_read_feedback(as_user, make_client, ids):
    kiosk = pair(as_user, make_client, ids)
    assert kiosk.get("/admin/feedback").status_code == 401


def test_form_facts_show_what_is_recorded(as_user, make_client):
    facts = as_user("bharat").get("/feedback/form").json()
    assert facts["username"] == "bharat" and facts["software_version"] and facts["commit"]
    assert facts["max_files"] == 5 and facts["email_copy"] is False
    assert make_client().get("/feedback/form").status_code == 401


def test_message_is_not_in_any_other_admin_response(as_user):
    send(as_user("bharat"), message=SECRET)
    admin = as_user("admin")
    for path in ("/admin/audit", "/admin/events", "/admin/overview", "/admin/settings", "/admin/users"):
        r = admin.get(path)
        assert SECRET not in r.text, path


# ---- e-mail outbox -------------------------------------------------------------------------


@pytest.fixture
def mail_settings(settings):
    from dataclasses import replace

    return replace(
        settings,
        feedback_email="admins@lab.example.in",
        smtp_host="mail.lab.example.in",
        smtp_from="labadda@lab.example.in",
    )


class Outbox:
    def __init__(self):
        self.sent, self.fail = [], None

    def __call__(self, settings, message):
        if self.fail:
            raise self.fail
        self.sent.append(message)


def run_outbox(db_factory, app, mail_settings, outbox, when=None):
    return feedback_mail.process_outbox(
        db_factory, mail_settings, app.state.assets, send=outbox, now=lambda: when or utcnow()
    )


def test_email_has_all_metadata_message_and_files(as_user, db_factory, app, mail_settings):
    send(as_user("bharat"), files=[("shot.png", png(), "image/png"), ("log.txt", b"trace\n", "text/plain")])
    box = Outbox()
    assert run_outbox(db_factory, app, mail_settings, box) == 1
    mail = box.sent[0]
    assert mail["To"] == "admins@lab.example.in" and mail["From"] == "labadda@lab.example.in"
    assert "problem from bharat" in mail["Subject"]
    body = mail.get_body().get_content()
    for needle in (
        "From: bharat",
        "Kind: problem",
        "Page: /w/thin-films/board",
        "Screen: 1920x1080",
        "Software version:",
        "Commit:",
        "Browser:",
        SECRET,
    ):
        assert needle in body
    assert sorted(p.get_filename() for p in mail.iter_attachments()) == ["log.txt", "shot.png"]
    with db_factory() as db:
        row = db.query(FeedbackMail).one()
        assert row.status == "sent" and row.attempts == 1 and row.sent_at is not None
    assert run_outbox(db_factory, app, mail_settings, box) == 0  # nothing is sent twice


def test_email_lists_files_that_exceed_the_attachment_cap(
    as_user, db_factory, app, mail_settings, monkeypatch
):
    monkeypatch.setattr(feedback_mail, "MAX_ATTACHED_BYTES", 12)
    send(
        as_user("bharat"),
        files=[("a.txt", b"0123456789", "text/plain"), ("b.txt", b"abcdefghij", "text/plain")],
    )
    box = Outbox()
    run_outbox(db_factory, app, mail_settings, box)
    mail = box.sent[0]
    assert [p.get_filename() for p in mail.iter_attachments()] == ["a.txt"]
    body = mail.get_body().get_content()
    assert "Not attached" in body and "b.txt" in body and "console" in body


def test_retry_with_backoff_then_failed_with_a_plain_reason(as_user, db_factory, app, mail_settings):
    send(as_user("bharat"))
    box = Outbox()
    box.fail = smtplib.SMTPAuthenticationError(535, b"5.7.8 password for admins@lab.example.in wrong")
    now = utcnow()
    for attempt in range(feedback_mail.MAX_ATTEMPTS):
        assert run_outbox(db_factory, app, mail_settings, box, when=now) == 0
        with db_factory() as db:
            row = db.query(FeedbackMail).one()
            assert row.attempts == attempt + 1
            if attempt + 1 < feedback_mail.MAX_ATTEMPTS:
                wait = timedelta(minutes=feedback_mail.BACKOFF_MINUTES[attempt])
                assert row.status == "queued" and row.next_attempt_at == now + wait
                # Not due again until the wait has passed.
                assert (
                    run_outbox(db_factory, app, mail_settings, box, when=now + wait - timedelta(seconds=1))
                    == 0
                )
                assert db.query(FeedbackMail).one().attempts == attempt + 1
                now = now + wait
    with db_factory() as db:
        row = db.query(FeedbackMail).one()
        assert row.status == "failed" and "refused the sign-in" in row.last_error
        assert "admins@" not in row.last_error and "password" not in row.last_error.lower().replace(
            "password.", ""
        )
    admin = as_user("admin")
    listing = admin.get("/admin/feedback").json()
    assert listing["items"][0]["email"]["status"] == "failed"
    # An administrator can queue it again; it then goes out.
    fid = listing["items"][0]["id"]
    assert admin.post(f"/admin/feedback/{fid}/resend").status_code == 200
    box.fail = None
    assert run_outbox(db_factory, app, mail_settings, box) == 1
    assert admin.post(f"/admin/feedback/{fid}/resend").status_code == 409


def test_mail_failure_never_blocks_or_fails_the_submission(as_user, db_factory, app, mail_settings):
    box = Outbox()
    box.fail = OSError("relay down")
    assert send(as_user("bharat")).status_code == 201
    run_outbox(db_factory, app, mail_settings, box)
    with db_factory() as db:
        assert db.query(Feedback).count() == 1
        assert db.query(FeedbackMail).one().last_error == "The mail server could not be reached."


def test_unconfigured_mail_leaves_rows_waiting(as_user, db_factory, app, settings):
    send(as_user("bharat"))
    box = Outbox()
    assert feedback_mail.process_outbox(db_factory, settings, app.state.assets, send=box) == 0
    with db_factory() as db:
        row = db.query(FeedbackMail).one()
        assert row.status == "queued" and row.attempts == 0 and not box.sent


def test_reasons_never_echo_server_text():
    refused = smtplib.SMTPResponseException(554, b"relay denied for secret@lab.example.in")
    assert feedback_mail.plain_reason(refused) == "The mail server refused the message (code 554)."
    assert feedback_mail.plain_reason(TimeoutError()) == "The mail server did not answer in time."
    assert feedback_mail.plain_reason(ValueError("x")) == "The message could not be sent."


def test_smtp_send_uses_only_the_configured_relay(mail_settings, monkeypatch):
    from dataclasses import replace
    from email.message import EmailMessage

    calls = []

    class FakeSMTP:
        def __init__(self, host, port, timeout):
            calls.append(("connect", host, port, timeout))

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def ehlo(self):
            calls.append(("ehlo",))

        def starttls(self, context):
            calls.append(("starttls",))

        def login(self, user, password):
            calls.append(("login", user, password))

        def send_message(self, message):
            calls.append(("send", message["To"]))

    monkeypatch.setattr(smtplib, "SMTP", FakeSMTP)
    configured = replace(
        mail_settings, smtp_port=2525, smtp_starttls=True, smtp_user="relay", smtp_password="s3cret"
    )
    message = EmailMessage()
    message["To"] = configured.feedback_email
    feedback_mail.smtp_send(configured, message)
    assert calls[0] == ("connect", "mail.lab.example.in", 2525, feedback_mail.SMTP_TIMEOUT_SECONDS)
    assert ("starttls",) in calls and ("login", "relay", "s3cret") in calls and calls[-1][0] == "send"


@pytest.fixture
def scratch_url(migrated):
    yield migrated
    recreate_schema(migrated)
    command.upgrade(alembic_config(migrated), "head")


def test_downgrade_refuses_while_feedback_exists(scratch_url, ids, db_factory):
    cfg = alembic_config(scratch_url)
    with db_factory() as db:
        db.add(
            Feedback(
                user_id=ids["users"]["bharat"],
                client_id="migration-test-1",
                username="bharat",
                created_at=utcnow(),
                category="problem",
                message="kept",
                software_version="0",
                commit="unknown",
            )
        )
        db.commit()
    with pytest.raises(Exception, match="Feedback exists"):
        command.downgrade(cfg, "0039")
    with db_factory() as db:
        db.execute(text("delete from feedback"))
        db.commit()
    command.downgrade(cfg, "0039")
    command.upgrade(cfg, "head")


def test_health_item_and_doctor_report_the_outbox(settings, mail_settings):
    from datetime import UTC, datetime

    from labadda import doctor
    from labadda.health.feedback_mail import evaluate
    from labadda.health.types import Context

    ctx = Context(settings=mail_settings, factory=None, started=utcnow(), expected_schema=lambda: "x")
    assert evaluate(ctx, queued=2, failed=0, oldest_wait=timedelta(minutes=1)).status == "healthy"
    assert evaluate(ctx, queued=2, failed=0, oldest_wait=timedelta(hours=2)).status == "degraded"
    assert evaluate(ctx, queued=0, failed=1, oldest_wait=None).status == "degraded"
    host = doctor.Host(environ={}, now=lambda: datetime.now(UTC), outbox=lambda url: (3, 1))
    assert doctor.check_mail(host, settings).status == "skip"
    failed = doctor.check_mail(host, mail_settings)
    assert failed.status == "fail" and "1 feedback e-mails" in failed.summary
    host.outbox = lambda url: (0, 0)
    assert doctor.check_mail(host, mail_settings).status == "pass"
    host.outbox = lambda url: None
    assert doctor.check_mail(host, mail_settings).status == "fail"
