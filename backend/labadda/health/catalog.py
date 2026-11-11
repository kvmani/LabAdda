"""The ten health items of AD-07, in display order, with the help page and chart behind each."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from . import (
    application,
    backups,
    certificate,
    connections,
    database,
    file_storage,
    jobs,
    response_time,
    server,
    sign_in,
)
from .types import Context, Result


@dataclass(frozen=True)
class Chart:
    """The stored series drawn under an item (AD-04): a catalogued metric and dimension."""

    metric: str
    dimension: str
    unit: str


@dataclass(frozen=True)
class Item:
    key: str
    label: str
    check: Callable[[Context], Result]
    # Help page below help/troubleshooting/ that explains this item's event codes.
    help: str
    chart: Chart | None = None


ITEMS: tuple[Item, ...] = (
    Item("application", "Application", application.check, "health-application"),
    Item("database", "Database", database.check, "health-database", Chart("db.size_bytes", "", "bytes")),
    Item(
        "file_storage",
        "File storage",
        file_storage.check,
        "health-file-storage",
        Chart("disk.free_bytes", "", "bytes"),
    ),
    Item(
        "connections",
        "Live connections",
        connections.check,
        "health-live-connections",
        Chart("sockets.connected", "", "connections"),
    ),
    Item("jobs", "Background jobs", jobs.check, "health-background-jobs"),
    Item(
        "response_time",
        "Response time",
        response_time.check,
        "health-response-time",
        Chart("http.latency_p95", "all", "ms"),
    ),
    Item(
        "sign_in",
        "Sign-in",
        sign_in.check,
        "health-sign-in",
        Chart("auth.signin_failed", "", "failed sign-ins"),
    ),
    Item("backups", "Backups", backups.check, "health-backups"),
    Item("server", "Server", server.check, "health-server"),
    Item("certificate", "Certificate", certificate.check, "health-certificate"),
)
BY_KEY = {item.key: item for item in ITEMS}
