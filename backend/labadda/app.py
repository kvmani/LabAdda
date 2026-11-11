"""ASGI application factory. Root and prefixed instances use the same code."""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory
from fastapi import APIRouter, FastAPI, Request, WebSocket
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from sqlalchemy import text

from . import boardstate, metrics, scheduler
from .api import (
    admin,
    alert_preferences,
    auth,
    board,
    capabilities,
    changes,
    chat,
    dashboard,
    files,
    governance,
    groups,
    inventory_jobs,
    notes,
    notifications,
    panel,
    people,
    posts,
    task_assignment,
    task_board_conversion,
    task_comments,
    task_conversion,
    todos,
    usage,
    workspaces,
)
from .api import (
    audit as audit_api,
)
from .api import (
    metrics as metrics_api,
)
from .config import Settings, get_settings
from .db import session_factory
from .errors import ApiError
from .realtime import Hub
from .storage import AssetStore

log = logging.getLogger("labadda")
MIGRATIONS = Path(__file__).resolve().parents[1] / "migrations"


def expected_schema_head() -> str:
    cfg = Config()
    cfg.set_main_option("script_location", str(MIGRATIONS))
    return ScriptDirectory.from_config(cfg).get_current_head()


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    factory = session_factory(settings.database_url)
    store = AssetStore(settings.asset_dir)
    hub = Hub(factory, settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        hub.loop = asyncio.get_running_loop()
        task = None
        if settings.run_scheduler:

            def cleanup():
                with factory() as db:
                    files.cleanup_provisional(db, store, settings)
                with factory() as db:
                    boardstate.compact_all(
                        db, settings.board_compact_threshold, settings.board_keep_revisions
                    )

            collector = metrics.Collector(factory, settings, lambda: len(hub.connections))
            task = asyncio.create_task(
                scheduler.run_forever(factory, settings.reminder_interval_seconds, (cleanup, collector.tick))
            )
        yield
        if task:
            task.cancel()

    app = FastAPI(
        title="LabAdda",
        version="0.1.0",
        lifespan=lifespan,
        docs_url=None,
        redoc_url=None,
        openapi_url=f"{settings.api_prefix}/openapi.json",
    )
    app.state.settings = settings
    app.state.session_factory = factory
    app.state.assets = store
    app.state.hub = hub

    @app.exception_handler(ApiError)
    async def api_error(_: Request, exc: ApiError):
        return JSONResponse({"error": {"code": exc.code, "message": exc.message}}, status_code=exc.status)

    @app.exception_handler(RequestValidationError)
    async def validation_error(_: Request, exc: RequestValidationError):
        fields = [
            {"field": ".".join(str(p) for p in e["loc"][1:]), "message": e["msg"]} for e in exc.errors()
        ]
        return JSONResponse(
            {"error": {"code": "invalid", "message": "Some fields are invalid.", "fields": fields}},
            status_code=422,
        )

    @app.middleware("http")
    async def request_log(request: Request, call_next):
        request_id = request.headers.get("x-request-id") or uuid.uuid4().hex[:16]
        started = time.perf_counter()
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        if request.url.path.startswith(settings.api_prefix):
            response.headers.setdefault("Cache-Control", "private, no-store")
        # Operational log: no bodies, tokens or query strings.
        log.info(
            json.dumps(
                {
                    "event": "http",
                    "request_id": request_id,
                    "method": request.method,
                    "route": request.scope.get("route").path if request.scope.get("route") else "-",
                    "status": response.status_code,
                    "ms": round((time.perf_counter() - started) * 1000, 1),
                }
            )
        )
        return response

    app.add_middleware(metrics.MetricsMiddleware, api_prefix=settings.api_prefix)

    api = APIRouter(prefix=settings.api_prefix)
    for module in (
        auth,
        alert_preferences,
        dashboard,
        workspaces,
        admin,
        audit_api,
        people,
        governance,
        usage,
        inventory_jobs,
        metrics_api,
        capabilities,
        groups,
        task_assignment,
        task_comments,
        task_conversion,
        task_board_conversion,
        todos,
        posts,
        files,
        notes,
        notifications,
        chat,
        changes,
        board,
        panel,
    ):
        api.include_router(module.router)
    app.include_router(api)

    base = settings.base_path

    @app.get(f"{base}/healthz", include_in_schema=False)
    def liveness():
        return {"status": "ok"}

    @app.get(f"{base}/readyz", include_in_schema=False)
    def readiness():
        try:
            with factory() as db:
                current = db.execute(text("select version_num from alembic_version")).scalar()
        except Exception:  # noqa: BLE001 — readiness reports any database failure as unavailable
            return JSONResponse({"status": "unavailable"}, status_code=503)
        if current != expected_schema_head():
            return JSONResponse({"status": "schema_mismatch"}, status_code=503)
        return {"status": "ready"}

    @app.websocket(f"{base}/ws/")
    async def socket(ws: WebSocket):
        await hub.serve(ws)

    _mount_frontend(app, settings)
    return app


def _mount_frontend(app: FastAPI, settings: Settings) -> None:
    dist = settings.frontend_dist
    base = settings.base_path

    def shell() -> HTMLResponse:
        if dist is None or not (dist / "index.html").exists():
            return HTMLResponse(
                "<!doctype html><title>LabAdda</title><p>Frontend not built. "
                "Run <code>npm run build</code> in frontend/.</p>",
                status_code=503,
            )
        html = (dist / "index.html").read_text()
        config = json.dumps({"base": base, "instance": settings.instance})
        inject = f'<base href="{base}/"><script>window.__LABADDA__={config}</script>'
        return HTMLResponse(
            html.replace("<head>", "<head>" + inject, 1), headers={"Cache-Control": "no-cache"}
        )

    if base:

        @app.get(base, include_in_schema=False)
        def base_redirect():
            return RedirectResponse(f"{base}/", status_code=308)

    @app.get(f"{base}/assets/{{path:path}}", include_in_schema=False)
    def static_asset(path: str):
        if dist is None:
            return JSONResponse({"error": {"code": "not_found", "message": "Not found."}}, status_code=404)
        root = (dist / "assets").resolve()
        target = (root / path).resolve()
        if root not in target.parents or not target.is_file():
            return JSONResponse({"error": {"code": "not_found", "message": "Not found."}}, status_code=404)
        return FileResponse(target, headers={"Cache-Control": "public, max-age=31536000, immutable"})

    @app.get(f"{base}/{{path:path}}", include_in_schema=False)
    def spa(path: str):
        if path.startswith(("api/", "ws/")):
            return JSONResponse({"error": {"code": "not_found", "message": "Not found."}}, status_code=404)
        if dist is not None and path and "/" not in path:
            candidate = dist / path
            if candidate.is_file() and candidate.suffix in {".ico", ".svg", ".png", ".txt"}:
                return FileResponse(candidate)
        return shell()
