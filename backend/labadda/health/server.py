"""Server: process memory, host load and host memory, read from /proc."""

from __future__ import annotations

from .proc import ProcUnavailable
from .types import Context, Result, make


def evaluate(
    ctx: Context, *, process_bytes: int, load: float, cpus: int, memory_total: int, memory_free: int
) -> Result:
    limits = ctx.settings.health
    process_mb = process_bytes / 1024**2
    per_cpu = load / cpus
    used_percent = (memory_total - memory_free) * 100 / memory_total
    detail = (
        f"LabAdda uses {process_mb:.0f} MB. The computer's load is {load:.2f} on {cpus} processors "
        f"and {used_percent:.0f} % of its memory is in use."
    )
    problems = []
    if process_mb > limits.process_memory_mb:
        problems.append("LabAdda is using a lot of memory.")
    if per_cpu * 10 > limits.load_per_cpu_x10:
        problems.append("The computer is busy.")
    if used_percent > limits.host_memory_percent:
        problems.append("The computer is short of memory.")
    status = "degraded" if problems else "healthy"
    return make(ctx, status, round(process_mb), "MB", " ".join([*problems, detail]))


def check(ctx: Context) -> Result:
    try:
        total, free = ctx.proc.memory()
        return evaluate(
            ctx,
            process_bytes=ctx.proc.process_rss_bytes(),
            load=ctx.proc.load_average(),
            cpus=ctx.proc.cpu_count(),
            memory_total=total,
            memory_free=free,
        )
    except ProcUnavailable:
        return make(ctx, "unsupported", None, "MB", "This computer does not report these figures.")
