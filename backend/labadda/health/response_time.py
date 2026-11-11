"""Response time: p50 and p95 of API requests over 5 minutes, and the server-error rate."""

from __future__ import annotations

from ..metrics import catalog
from . import windows
from .types import Context, Result, make

WINDOW_MINUTES = 5
# A single failure among a handful of requests says nothing about the error rate.
MIN_REQUESTS_FOR_RATE = 20
METRICS = {"http.requests", "http.errors", "http.latency_p50", "http.latency_p95"}


def evaluate(ctx: Context, *, requests: float, errors: float, p50: float | None, p95: float | None) -> Result:
    limits = ctx.settings.health
    if not requests or p50 is None or p95 is None:
        return make(ctx, "unknown", None, "ms", "No requests were recorded in the last 5 minutes.")
    rate = errors * 100 / requests
    detail = (
        f"Median {round(p50)} ms over {round(requests)} requests in the last 5 minutes; "
        f"{rate:.1f} % ended in a server error."
    )
    problems = []
    if p95 > limits.response_p95_ms:
        problems.append(f"The slowest 5 % take more than {limits.response_p95_ms} ms.")
    if requests >= MIN_REQUESTS_FOR_RATE and rate > limits.error_rate_percent:
        problems.append(f"More than {limits.error_rate_percent} % of requests failed.")
    status = "degraded" if problems else "healthy"
    return make(ctx, status, round(p95), "ms", " ".join([*problems, detail]))


def check(ctx: Context) -> Result:
    try:
        rows = windows.recent_minutes(ctx, WINDOW_MINUTES, METRICS)
    except Exception:  # noqa: BLE001 — stored minutes need the database
        return make(ctx, "unknown", None, "ms", "Recent response times could not be read.")
    return evaluate(
        ctx,
        requests=windows.total(rows, "http.requests"),
        errors=windows.total(rows, "http.errors"),
        p50=windows.weighted_mean(rows, "http.latency_p50", catalog.ALL_ROUTES),
        p95=windows.weighted_mean(rows, "http.latency_p95", catalog.ALL_ROUTES),
    )
