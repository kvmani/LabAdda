"""Health thresholds (AD-07): settings with the contract defaults, read from the environment.

Kept apart from ``config`` so that the list of knobs and their documented defaults stay in one
short place. Every field has an environment variable of the same name in upper case, prefixed
with ``LABADDA_HEALTH_``, and is described in ``deploy/labadda.env.example``.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, fields

GIB = 1024**3


@dataclass(frozen=True)
class HealthThresholds:
    sample_seconds: int = 15  # how often the background sampler measures every item
    stale_seconds: int = 60  # a result older than this is shown as stale
    db_slow_ms: int = 250  # database round trip above this is degraded
    db_connections_percent: int = 80  # share of the connection limit in use that is degraded
    disk_reserve_bytes: int = 5 * GIB  # free space reserve on the asset volume
    inode_reserve_percent: int = 5  # free-inode reserve on the asset volume
    queue_backlog: int = 1000  # queued live messages beyond this is degraded (5 times is unavailable)
    job_stall_degraded_seconds: int = 120  # no scheduler tick completed for this long is degraded
    job_stall_unavailable_seconds: int = 600  # ... and this long is unavailable
    job_failures_per_hour: int = 3  # failed scheduled jobs in the last hour that are degraded
    response_p95_ms: int = 1000  # API p95 above this over 5 minutes is degraded
    error_rate_percent: int = 2  # share of API requests failing with a server error
    signin_failure_percent: int = 50  # share of failed sign-ins over 15 minutes that is degraded
    backup_fresh_hours: int = 26  # newer than this is healthy
    backup_stale_hours: int = 50  # older than this is unavailable
    certificate_degraded_days: int = 30
    certificate_unavailable_days: int = 7
    certificate_fresh_hours: int = 72  # a certificate status file older than this is stale
    process_memory_mb: int = 1024
    load_per_cpu_x10: int = 20  # host load per processor, in tenths (20 means 2.0)
    host_memory_percent: int = 90


def load_thresholds(environ: Mapping[str, str]) -> HealthThresholds:
    """Read each threshold from ``LABADDA_HEALTH_<NAME>``; a bad value stops start-up with its name."""
    values = {}
    for field in fields(HealthThresholds):
        name = "LABADDA_HEALTH_" + field.name.upper()
        raw = environ.get(name)
        if raw is None:
            continue
        number = int(raw)
        if number < 1:
            raise ValueError(f"{name} must be a positive integer")
        values[field.name] = number
    return HealthThresholds(**values)
