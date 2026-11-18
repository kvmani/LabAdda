"""File storage: free space and free inodes on the asset volume, against the configured reserve."""

from __future__ import annotations

from .types import Context, DiskReading, Result, human_bytes, make

MARGIN = 1.2  # degraded from reserve + 20 % (AD-07)


def evaluate(ctx: Context, reading: DiskReading) -> Result:
    limits = ctx.settings.health
    reserve = limits.disk_reserve_bytes
    inode_percent = None
    if reading.free_inodes is not None and reading.total_inodes and reading.total_inodes > 0:
        inode_percent = reading.free_inodes * 100 / reading.total_inodes
    slots = (
        f"{inode_percent:.0f} % of file slots free"
        if inode_percent is not None
        else "file-slot availability is not measured on this volume"
    )
    detail = (
        f"{human_bytes(reading.free_bytes)} free of {human_bytes(reading.total_bytes)}; "
        f"{slots}. The reserve is {human_bytes(reserve)}."
    )
    if reading.free_bytes < reserve or (
        inode_percent is not None and inode_percent < limits.inode_reserve_percent
    ):
        return make(ctx, "unavailable", reading.free_bytes, "bytes", "Below the reserve. " + detail)
    if reading.free_bytes < reserve * MARGIN or (
        inode_percent is not None and inode_percent < limits.inode_reserve_percent * MARGIN
    ):
        return make(ctx, "degraded", reading.free_bytes, "bytes", "Close to the reserve. " + detail)
    return make(
        ctx, "healthy" if inode_percent is not None else "unknown", reading.free_bytes, "bytes", detail
    )


def check(ctx: Context) -> Result:
    try:
        reading = ctx.disk(ctx.settings.asset_dir)
    except (OSError, AttributeError):
        return make(ctx, "unknown", None, "bytes", "The file storage volume could not be measured.")
    return evaluate(ctx, reading)
