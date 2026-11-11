"""Count API requests, server errors and latency by route group.

The group comes from the matched route template, never from the raw path, so IDs, names and
query strings cannot become dimensions. Probes, static assets, the web shell and sockets are
outside the API prefix and are not counted.
"""

from __future__ import annotations

import time
from functools import lru_cache

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from . import catalog
from .registry import REGISTRY, Registry


@lru_cache(maxsize=512)
def route_group(template: str | None, api_prefix: str) -> str:
    """Map a route template such as ``/api/v1/workspaces/{id}/chat`` to a catalogued group."""
    if not template or not template.startswith(api_prefix + "/"):
        return catalog.OTHER_ROUTES
    static = [part for part in template[len(api_prefix) :].split("/") if part and not part.startswith("{")]
    if not static:
        return catalog.OTHER_ROUTES
    if static[0] == "workspaces" and len(static) > 1:
        return catalog.ROUTE_GROUPS.get(f"workspaces/{static[1]}", catalog.ROUTE_GROUPS["workspaces"])
    return catalog.ROUTE_GROUPS.get(static[0], catalog.OTHER_ROUTES)


class MetricsMiddleware:
    """Pure ASGI middleware: no request body is read and nothing is buffered."""

    def __init__(self, app: ASGIApp, api_prefix: str, registry: Registry = REGISTRY) -> None:
        self.app = app
        self.api_prefix = api_prefix
        self.registry = registry

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or not scope["path"].startswith(self.api_prefix + "/"):
            await self.app(scope, receive, send)
            return
        started = time.perf_counter()
        status = 500

        async def send_with_status(message: Message) -> None:
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
            await send(message)

        try:
            await self.app(scope, receive, send_with_status)
        finally:
            self._record(scope, status, (time.perf_counter() - started) * 1000)

    def _record(self, scope: Scope, status: int, elapsed_ms: float) -> None:
        route = scope.get("route")
        group = route_group(getattr(route, "path", None), self.api_prefix)
        self.registry.count("http.requests", group)
        if status >= 500:
            self.registry.count("http.errors", group)
        self.registry.observe("http.latency", elapsed_ms, group)
        self.registry.observe("http.latency", elapsed_ms, catalog.ALL_ROUTES)
