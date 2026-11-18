#!/usr/bin/env python3
"""Reviewable site configuration and bounded operational probes (stdlib only)."""

from __future__ import annotations

import argparse
import json
import os
import re
import signal
import ssl
import sys
import urllib.error
import urllib.request
from contextlib import contextmanager
from pathlib import Path

# Operator tools run as `python -I` and are also loaded by path in tests; neither puts this folder on
# the import path, so the sibling module is found explicitly.
if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
from service_files import nginx_files, unit_file


class OperationsError(Exception):
    """Invalid site input or an unsuccessful operational gate."""


FIELDS = {
    "instance",
    "root",
    "user",
    "group",
    "env_file",
    "server_name",
    "port",
    "base_path",
    "tls_certificate",
    "tls_key",
    "backup_root",
}
# "web_access": "shared-http" serves LabAdda under a URL prefix inside another application's plain-HTTP
# nginx site (for example an IP address already used by project_management_software). Absent means the
# dedicated HTTPS server block, so site files written before the option existed keep their meaning.
# "web_access": "dedicated-http" is this server's own plain-HTTP site (an IP address, no certificate).
# "service_scope": "user" runs LabAdda as the operator's own systemd user services, like
# project_management_software; absent means the original system unit run by a dedicated account.
OPTIONAL_FIELDS = {"web_access", "service_scope"}
WEB_ACCESS = ("https", "shared-http", "dedicated-http")
SERVICE_SCOPES = ("system", "user")
PATH_FIELDS = {"root", "env_file", "tls_certificate", "tls_key", "backup_root"}
NAME = re.compile(r"[a-z][a-z0-9_-]{0,31}\Z")
PATH = re.compile(r"/[A-Za-z0-9_./-]+\Z")


def load_site(path: Path) -> dict:  # noqa: PLR0912 — linear operator script; steps run in a fixed order
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise OperationsError("Duplicate site configuration key")
            result[key] = value
        return result

    try:
        site = json.loads(path.read_text(), object_pairs_hook=unique)
    except (ValueError, OSError) as error:
        raise OperationsError("Cannot read site configuration") from error
    if not isinstance(site, dict) or not FIELDS <= set(site) <= FIELDS | OPTIONAL_FIELDS:
        raise OperationsError("Site configuration must contain exactly the documented fields")
    if site.setdefault("web_access", "https") not in WEB_ACCESS:
        raise OperationsError("web_access must be https, dedicated-http or shared-http")
    if site.setdefault("service_scope", "system") not in SERVICE_SCOPES:
        raise OperationsError("service_scope must be system or user")
    for field in ("instance", "user", "group"):
        if not isinstance(site[field], str) or not NAME.fullmatch(site[field]):
            raise OperationsError(f"Invalid {field}")
    if site["user"] == "root" or site["group"] == "root":
        raise OperationsError("Runtime identity must be unprivileged")
    for field in PATH_FIELDS:
        value = site[field]
        if (
            not isinstance(value, str)
            or not PATH.fullmatch(value)
            or any(p in ("", ".", "..") for p in value[1:].split("/"))
        ):
            raise OperationsError(f"Invalid absolute {field}")
    if type(site["port"]) is not int or not 1024 <= site["port"] <= 65535:
        raise OperationsError("Port must be an unprivileged TCP port")
    host = site["server_name"]
    if not isinstance(host, str) or len(host) > 253 or not re.fullmatch(r"[a-z0-9]+(?:[.-][a-z0-9]+)*", host):
        raise OperationsError("Invalid server DNS name")
    base = site["base_path"]
    if not isinstance(base, str) or (base and not re.fullmatch(r"(?:/[A-Za-z0-9_-]+)+", base)):
        raise OperationsError("Invalid URL prefix")
    if site["web_access"] == "shared-http" and not base:
        raise OperationsError("A shared site needs a URL prefix such as /labadda")
    root, backup = Path(site["root"]), Path(site["backup_root"])
    forbidden_roots = ("/home", "/root", "/tmp", "/var/tmp")  # noqa: S108 — a denylist, not a temp file
    if any(root.is_relative_to(Path(p)) for p in forbidden_roots):
        raise OperationsError(
            "System service requires a persistent root outside home and temporary directories"
        )
    if root.is_relative_to(backup) or backup.is_relative_to(root):
        raise OperationsError("Backup root must be separate from the instance root")
    for field in ("env_file", "tls_certificate", "tls_key"):
        if Path(site[field]).is_relative_to(root) or Path(site[field]).is_relative_to(backup):
            raise OperationsError("Configuration and TLS keys must be outside the instance root")
    if len({site[f] for f in ("env_file", "tls_certificate", "tls_key")}) != 3:
        raise OperationsError("Configuration and TLS files must be distinct")
    return site


def render(site: dict) -> dict[str, str]:
    root = site["root"]
    unit = unit_file(site)
    web = nginx_files(site)
    plan = {
        "format": 1,
        "service": f"labadda-{site['instance']}.service",
        "directories": {
            "public_0755": [root, root + "/releases", root + "/traffic"],
            "private_runtime_0700": [root + "/assets"],
            "private_operator_0700": [root + "/operations", site["backup_root"]],
        },
        "required_gates": [
            "Dedicated PostgreSQL 16 database and least-privilege role",
            "Private environment file, unique cookie, secure HTTPS origin and matching prefix",
            "CA-trusted certificate and key; nginx -t; systemd-analyze verify",
            "Verified offline release installed with release.py; migrate while writers stopped",
            "Backup and isolated restore rehearsal, independently stored trusted digests",
            "Direct readiness before lifting maintenance; TLS readiness and WebSocket qualification",
            "Off-host backup transfer and site/device/owner acceptance",
        ],
    }
    return {"service.conf": unit, **web, "plan.json": json.dumps(plan, indent=2) + "\n"}


def service_command(site: dict, *args: str) -> tuple[list[str], dict[str, str]]:
    """The systemctl call and environment for this site's own units.

    A user-scope site is driven by its service account itself (its timer, or the installer through
    runuser), so only that account's user manager is addressed; it is found through XDG_RUNTIME_DIR
    because callers run with a cleared environment."""
    env = {"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8"}
    if site.get("service_scope") == "user":
        env["XDG_RUNTIME_DIR"] = f"/run/user/{os.getuid()}"
        return ["systemctl", "--user", *args], env
    return ["systemctl", *args], env


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: PLR0917 — stdlib override signature
        return None


@contextmanager
def deadline(seconds: int):
    """Linux operator CLI wall-clock deadline, including trickled response bodies."""
    if not hasattr(signal, "SIGALRM"):
        raise OperationsError("Managed site probes require Linux wall-clock deadlines")

    def expired(signum, frame):
        raise TimeoutError("Operational probe deadline exceeded")

    previous = signal.signal(signal.SIGALRM, expired)
    signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous)


def probe(site: dict, *, direct: bool = False, ca_file: str | None = None) -> dict:
    scheme = "https" if site.get("web_access", "https") == "https" else "http"
    origin = f"http://127.0.0.1:{site['port']}" if direct else f"{scheme}://{site['server_name']}"
    # A pilot may use a self-signed or private-CA certificate the server's own trust store does not
    # list; the installer records its file here so scheduled backups and upgrades can confirm TLS too.
    context = ssl.create_default_context(cafile=ca_file or os.environ.get("LABADDA_PROBE_CA_FILE") or None)
    opener = urllib.request.build_opener(
        urllib.request.ProxyHandler({}), NoRedirect(), urllib.request.HTTPSHandler(context=context)
    )
    checks = {}
    for endpoint, expected in (("healthz", "ok"), ("readyz", "ready")):
        try:
            with (
                deadline(10),
                opener.open(origin + site["base_path"] + "/" + endpoint, timeout=10) as response,
            ):
                payload = response.read(4097)
                checks[endpoint] = (
                    response.status == 200
                    and len(payload) <= 4096
                    and json.loads(payload) == {"status": expected}
                )
        except (OSError, ValueError, urllib.error.URLError):
            checks[endpoint] = False
    return {
        "format": 1,
        "instance": site["instance"],
        "route": "loopback" if direct else ("tls" if scheme == "https" else site["web_access"]),
        "checks": checks,
        "passed": all(checks.values()),
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--site", type=Path, required=True)
    sub = parser.add_subparsers(dest="command", required=True)
    output = sub.add_parser("render", help="Write a new review directory; never install host configuration")
    output.add_argument("--out", type=Path, required=True)
    health = sub.add_parser(
        "probe", help="Bounded exact health/readiness probes; no redirects or proxy environment"
    )
    health.add_argument("--direct", action="store_true")
    health.add_argument("--ca-file")
    args = parser.parse_args(argv)
    try:
        site = load_site(args.site)
        if args.command == "render":
            args.out.mkdir(mode=0o700)  # exclusive directory: never clobber an approved configuration
            for name, content in render(site).items():
                with (args.out / name).open("x") as target:
                    target.write(content)
            print(json.dumps({"rendered": str(args.out), "installed": False}))
            return 0
        report = probe(site, direct=args.direct, ca_file=args.ca_file)
        print(json.dumps(report))
        return 0 if report["passed"] else 1
    except (OperationsError, OSError) as error:
        print(f"Operation refused: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
