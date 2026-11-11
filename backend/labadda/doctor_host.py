"""The real-world side of `labadda doctor`: database, disk, HTTP and TLS probes.

Each function answers one narrow question with a small value and never returns or raises
anything that could carry a credential (no URLs, no driver messages). `doctor.py` receives
these through `Host`, so its checks can be tested with plain fakes.
"""

from __future__ import annotations

import json
import os
import shutil
import socket
import ssl
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Literal

from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

from .app import expected_schema_head

PROBE_SECONDS = 10


@dataclass(frozen=True)
class DatabaseState:
    """Whether the database answered, and which schema revision it reports (None if unmigrated)."""

    reachable: bool
    revision: str | None = None


@dataclass(frozen=True)
class FetchState:
    """Outcome of asking an address for its health answer."""

    kind: Literal["ok", "unreachable", "bad_response", "untrusted"]


@dataclass(frozen=True)
class TlsState:
    """Outcome of a certificate-verifying connection and the days the certificate has left."""

    kind: Literal["ok", "unreachable", "untrusted"]
    days_left: int | None = None


def database_state(url: str) -> DatabaseState:
    """Connect with a short timeout and read the schema revision."""
    engine = create_engine(url, connect_args={"connect_timeout": 5})
    try:
        with engine.connect() as connection:
            connection.execute(text("select 1"))
            try:
                revision = connection.execute(text("select version_num from alembic_version")).scalar()
            except SQLAlchemyError:
                return DatabaseState(reachable=True, revision=None)
            return DatabaseState(reachable=True, revision=revision)
    except Exception:  # noqa: BLE001 — any driver failure means "not reachable"; its text may hold the URL
        return DatabaseState(reachable=False)
    finally:
        engine.dispose()


def release_schema_head() -> str:
    """The schema revision this release expects, from its own migration scripts."""
    return expected_schema_head()


def free_bytes(path: Path) -> int | None:
    """Free space on the volume holding `path`, or None when the path does not exist."""
    try:
        return shutil.disk_usage(path).free
    except OSError:
        return None


def can_write(path: Path) -> bool:
    """Whether this account may create files in the directory, judged without creating any."""
    return path.is_dir() and os.access(path, os.W_OK | os.X_OK)


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def fetch_health(url: str, expected: str) -> FetchState:
    """GET a health address and require the exact `{"status": expected}` answer."""
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect())
    try:
        with opener.open(url, timeout=PROBE_SECONDS) as response:
            payload = response.read(4097)
            good = (
                response.status == 200
                and len(payload) <= 4096
                and json.loads(payload) == {"status": expected}
            )
            return FetchState("ok" if good else "bad_response")
    except urllib.error.URLError as error:
        if isinstance(error.reason, ssl.SSLError):
            return FetchState("untrusted")
        return FetchState("unreachable")
    except ValueError:
        return FetchState("bad_response")
    except OSError:
        return FetchState("unreachable")


def inspect_certificate(hostname: str, port: int, now: datetime) -> TlsState:
    """Open a verified TLS connection with the system trust store and read the expiry."""
    context = ssl.create_default_context()
    try:
        with (
            socket.create_connection((hostname, port), timeout=PROBE_SECONDS) as raw,
            context.wrap_socket(raw, server_hostname=hostname) as secure,
        ):
            certificate = secure.getpeercert()
    except ssl.SSLError:
        return TlsState("untrusted")
    except OSError:
        return TlsState("unreachable")
    expires = ssl.cert_time_to_seconds(certificate["notAfter"])
    return TlsState("ok", int((expires - now.timestamp()) // 86400))
