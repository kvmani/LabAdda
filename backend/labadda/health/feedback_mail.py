"""Feedback e-mail: messages waiting or failed in the outbox. Not set up is reported as such."""

from __future__ import annotations

from datetime import timedelta

from sqlalchemy import func, select, text

from ..models import FeedbackMail
from .types import Context, Result, make

UNIT = "waiting"
LATE = timedelta(minutes=30)


def evaluate(ctx: Context, *, queued: int, failed: int, oldest_wait: timedelta | None) -> Result:
    detail = f"{queued} waiting to be sent and {failed} that could not be sent."
    if failed:
        return make(ctx, "degraded", queued + failed, UNIT, "Some feedback could not be e-mailed. " + detail)
    if oldest_wait is not None and oldest_wait > LATE:
        return make(ctx, "degraded", queued, UNIT, "Feedback e-mail is running late. " + detail)
    return make(ctx, "healthy", queued, UNIT, detail)


def check(ctx: Context) -> Result:
    if not ctx.settings.mail_configured:
        return make(
            ctx, "unsupported", None, UNIT, "Feedback e-mail is not set up. Feedback is still saved here."
        )
    try:
        with ctx.factory() as db:
            db.execute(text("set local statement_timeout = '2s'"))
            counts = dict(
                db.execute(select(FeedbackMail.status, func.count()).group_by(FeedbackMail.status)).all()
            )
            first_due = db.scalar(
                select(func.min(FeedbackMail.next_attempt_at)).where(FeedbackMail.status == "queued")
            )
    except Exception:  # noqa: BLE001 — the outbox needs the database
        return make(ctx, "unknown", None, UNIT, "The feedback e-mail outbox could not be read.")
    wait = ctx.now() - first_due if first_due is not None else None
    return evaluate(ctx, queued=counts.get("queued", 0), failed=counts.get("failed", 0), oldest_wait=wait)
