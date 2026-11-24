"""Portable development/pilot serving; managed Linux installations keep their proxy contract."""

import asyncio
import sys
from pathlib import Path

import uvicorn


def serve(host: str, port: int, certfile: Path | None, keyfile: Path | None) -> None:
    """Use the Windows selector loop and optionally terminate local-pilot HTTPS."""
    loop = "auto"
    if sys.platform == "win32":
        policy = asyncio.WindowsSelectorEventLoopPolicy
        asyncio.set_event_loop_policy(policy())
        loop = "asyncio"
    uvicorn.run(
        "labadda.app:create_app",
        factory=True,
        host=host,
        port=port,
        loop=loop,
        ssl_certfile=str(certfile) if certfile else None,
        ssl_keyfile=str(keyfile) if keyfile else None,
        proxy_headers=True,
        forwarded_allow_ips="127.0.0.1",
        ws_max_size=64 * 1024,
        # One process by design: sign-in limits, live sockets, metrics and the scheduler are held
        # in memory. Pinned so a stray WEB_CONCURRENCY in the environment cannot split them.
        workers=1,
    )
