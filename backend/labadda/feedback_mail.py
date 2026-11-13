"""E-mail copies of feedback: an outbox worked by the scheduler, sent with the standard library.

This is the one outbound connection the product makes. It goes only to the intranet mail relay
the operator names in LABADDA_SMTP_HOST (owner-approved exception, AGENTS.md section 2).
A mail problem never blocks or fails a submission: the row is retried with growing waits and
then marked failed with a plain reason, and an administrator can queue it again.
"""

from __future__ import annotations

import logging
import smtplib
import socket
import ssl
from collections.abc import Callable
from datetime import datetime, timedelta
from email.message import EmailMessage

from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from .config import Settings
from .models import Asset, Feedback, FeedbackMail
from .security import utcnow
from .storage import AssetStore

log = logging.getLogger("labadda.feedback_mail")

BACKOFF_MINUTES = (1, 5, 15, 60, 240)
MAX_ATTEMPTS = len(BACKOFF_MINUTES) + 1
LEASE_MINUTES = 5
BATCH = 10
SMTP_TIMEOUT_SECONDS = 20
MAX_ATTACHED_BYTES = 10 * 1024 * 1024
SUBJECT_EXCERPT = 60

Sender = Callable[[Settings, EmailMessage], None]


def smtp_send(settings: Settings, message: EmailMessage) -> None:
    """Deliver one message through the configured relay, and nowhere else."""
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=SMTP_TIMEOUT_SECONDS) as relay:
        relay.ehlo()
        if settings.smtp_starttls:
            relay.starttls(context=ssl.create_default_context())
            relay.ehlo()
        if settings.smtp_user:
            relay.login(settings.smtp_user, settings.smtp_password)
        relay.send_message(message)


REASONS: tuple[tuple[type[Exception] | tuple[type[Exception], ...], str], ...] = (
    (
        smtplib.SMTPAuthenticationError,
        "The mail server refused the sign-in. Check the mail user name and password.",
    ),
    (
        (smtplib.SMTPRecipientsRefused, smtplib.SMTPSenderRefused),
        "The mail server refused the sender or recipient address.",
    ),
    ((TimeoutError, socket.timeout), "The mail server did not answer in time."),
    (ssl.SSLError, "The secure connection to the mail server could not be set up."),
)


def plain_reason(error: Exception) -> str:
    """A short sentence for the console; never the server's own text, which may echo addresses."""
    for kinds, sentence in REASONS:
        if isinstance(error, kinds):
            return sentence
    if isinstance(error, smtplib.SMTPResponseException):
        return f"The mail server refused the message (code {error.smtp_code})."
    if isinstance(error, OSError):  # SMTP errors are OSError too, so this must come last
        return "The mail server could not be reached."
    return "The message could not be sent."


def _one_line(text: str, limit: int) -> str:
    return " ".join(text.split())[:limit]


def _size(count: int) -> str:
    return f"{count / (1024 * 1024):.1f} MiB" if count >= 1024 * 1024 else f"{max(count // 1024, 1)} KiB"


def build_message(
    settings: Settings, row: Feedback, assets: list[Asset], store: AssetStore, when: datetime
) -> EmailMessage:
    """All metadata and the message; files attached up to a total cap, the rest listed."""
    message = EmailMessage()
    message["From"] = settings.smtp_from
    message["To"] = settings.feedback_email
    excerpt = _one_line(row.message, SUBJECT_EXCERPT)
    message["Subject"] = f"[LabAdda feedback] {row.category} from {row.username}: {excerpt}"
    attached, listed, used = [], [], 0
    for asset in assets:
        if used + asset.size <= MAX_ATTACHED_BYTES:
            attached.append(asset)
            used += asset.size
        else:
            listed.append(asset)
    lines = [
        f"From: {row.username}",
        f"Sent: {row.created_at.isoformat()}",
        f"Kind: {row.category}",
        f"Page: {row.route or 'not given'}",
        f"Software version: {row.software_version}",
        f"Commit: {row.commit}",
        f"Browser: {row.user_agent or 'not given'}",
        f"Screen: {row.screen or 'not given'}",
        f"Files: {len(assets)}",
        "",
        row.message,
    ]
    if listed:
        lines += [
            "",
            "Not attached to this e-mail (too large together). Open them in the LabAdda administrator",
        ]
        lines += ["console under Feedback:"]
        lines += [f"  - {a.display_name} ({_size(a.size)})" for a in listed]
    message.set_content("\n".join(lines))
    for asset in attached:
        data = store.path(asset.storage_key).read_bytes()
        main, sub = asset.media_type.split("/")
        message.add_attachment(data, maintype=main, subtype=sub, filename=asset.display_name)
    return message


def _claim(db: Session, now: datetime) -> list[FeedbackMail]:
    """Lease due rows so a slow relay or a second pass cannot send the same message twice."""
    rows = db.scalars(
        select(FeedbackMail)
        .where(FeedbackMail.status == "queued", FeedbackMail.next_attempt_at <= now)
        .order_by(FeedbackMail.next_attempt_at)
        .limit(BATCH)
        .with_for_update(skip_locked=True)
    ).all()
    for row in rows:
        row.next_attempt_at = now + timedelta(minutes=LEASE_MINUTES)
    db.commit()
    return rows


def process_outbox(
    factory: sessionmaker,
    settings: Settings,
    store: AssetStore,
    *,
    send: Sender = smtp_send,
    now: Callable[[], datetime] = utcnow,
) -> int:
    """Send what is due; returns how many were sent. Does nothing until mail is configured."""
    if not settings.mail_configured:
        return 0
    with factory() as db:
        claimed = [row.feedback_id for row in _claim(db, now())]
    sent = 0
    for feedback_id in claimed:
        sent += _deliver(factory, settings, store, feedback_id, send=send, now=now)
    return sent


def _deliver(factory, settings, store, feedback_id, *, send: Sender, now) -> int:
    with factory() as db:
        row = db.get(Feedback, feedback_id)
        assets = list(
            db.scalars(select(Asset).where(Asset.feedback_id == feedback_id).order_by(Asset.created_at))
        )
        try:
            send(settings, build_message(settings, row, assets, store, now()))
            error = None
        except Exception as caught:  # noqa: BLE001 — any failure is recorded and retried, never raised
            error = plain_reason(caught)
            log.warning("feedback_mail.failed", extra={"kind": type(caught).__name__})
        mail = db.get(FeedbackMail, feedback_id, with_for_update=True)
        mail.attempts += 1
        if error is None:
            mail.status, mail.sent_at, mail.last_error = "sent", now(), None
        else:
            mail.last_error = error
            if mail.attempts >= MAX_ATTEMPTS:
                mail.status = "failed"
            else:
                mail.next_attempt_at = now() + timedelta(minutes=BACKOFF_MINUTES[mail.attempts - 1])
        db.commit()
        return 1 if error is None else 0


def requeue(db: Session, feedback_id, now: datetime | None = None) -> FeedbackMail | None:
    """Give a failed message a fresh set of attempts."""
    mail = db.get(FeedbackMail, feedback_id, with_for_update=True)
    if mail is not None and mail.status == "failed":
        mail.status, mail.attempts, mail.last_error = "queued", 0, None
        mail.next_attempt_at = now or utcnow()
    return mail


def outbox_counts(db: Session) -> dict[str, int]:
    rows = db.execute(select(FeedbackMail.status, func.count()).group_by(FeedbackMail.status)).all()
    counts = {"queued": 0, "sent": 0, "failed": 0}
    counts.update(dict(rows))
    return counts


def outbox_job(factory: sessionmaker, settings: Settings, store: AssetStore) -> Callable[[], None]:
    def feedback_mail() -> None:
        process_outbox(factory, settings, store)

    return feedback_mail
