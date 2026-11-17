#!/usr/bin/env python3
"""Small, testable helpers for the on-server install scripts (standard library only).

install_helpers.py site-json ...   print the site description lifecycle.py and operations.py read
install_helpers.py env-file ...    print the private settings file from deploy/labadda.env.example
install_helpers.py status ...      print the one-screen summary facts as JSON
install_helpers.py attach-site ... add (or --remove) LabAdda's include line in a shared nginx site
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1] / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))
from labadda import backup_status  # noqa: E402 — needs the backend directory on sys.path first

SITE = re.compile(r"[a-z][a-z0-9]{0,19}\Z")
HOST = re.compile(r"[a-z0-9]+(?:[.-][a-z0-9]+)*\Z")
DOMAIN = re.compile(r"[a-z0-9]+(?:[.-][a-z0-9]+)*\Z")
ZONE = re.compile(r"[A-Za-z][A-Za-z0-9_+-]*(?:/[A-Za-z0-9_+-]+){0,2}\Z")
EMAIL = re.compile(r"[^@\s]+@[a-z0-9]+(?:[.-][a-z0-9]+)*\Z")


URL_PATH = re.compile(r"(?:/[a-z0-9][a-z0-9_-]*)+\Z")
WEB_ACCESS = ("https", "shared-http")
SERVER_BLOCK = re.compile(r"^\s*server\s*\{", re.MULTILINE)
SMTP_HOST = re.compile(r"[a-z0-9]+(?:[.-][a-z0-9]+)*\Z")


class InputError(ValueError):
    """An answer that cannot be used, phrased for the person typing it."""


def check_web(web_access: str, base_path: str) -> None:
    if web_access not in WEB_ACCESS:
        raise InputError("Web access: https (own hostname) or shared-http (another application's address).")
    if base_path and not URL_PATH.fullmatch(base_path):
        raise InputError("Address path: a path such as /labadda (lowercase, starting with /).")
    if web_access == "shared-http" and not base_path:
        raise InputError("Address path: a shared address needs its own path, for example /labadda.")


def check_answers(site: str, hostname: str, zone: str, domain: str, feedback: str = "") -> None:
    if not SITE.fullmatch(site):
        raise InputError("Site name: 1-20 lowercase letters or digits, starting with a letter.")
    if not HOST.fullmatch(hostname) or len(hostname) > 253:
        raise InputError(
            "Server address: a hostname or IP address (lowercase letters, digits, dots, hyphens)."
        )
    if not ZONE.fullmatch(zone):
        raise InputError("Time zone: a name such as Asia/Kolkata.")
    if domain and not DOMAIN.fullmatch(domain.lstrip("@")):
        raise InputError("E-mail domain: something like lab.example.in, without the @.")
    if feedback and not EMAIL.fullmatch(feedback):
        raise InputError("Feedback e-mail: an address such as admin@lab.example.in.")


def smtp_settings(
    relay: str, feedback: str, sender: str, *, starttls: bool, user: str, password_file: str
) -> dict:
    """Feedback e-mail settings from the relay answer `host[:port]`; blank means console only."""
    if not relay or not feedback:
        return {}
    host, _, port = relay.partition(":")
    if not SMTP_HOST.fullmatch(host) or (port and not (port.isdigit() and 0 < int(port) < 65536)):
        raise InputError("Mail relay: host or host:port, for example mail.lab.example.in:25.")
    if not EMAIL.fullmatch(sender):
        raise InputError("Mail 'from' address: an address such as labadda@lab.example.in.")
    values = {
        "LABADDA_FEEDBACK_EMAIL": feedback,
        "LABADDA_SMTP_HOST": host,
        "LABADDA_SMTP_PORT": port or "25",
        "LABADDA_SMTP_STARTTLS": "true" if starttls else "false",
        "LABADDA_SMTP_FROM": sender,
    }
    if user:
        values["LABADDA_SMTP_USER"] = user
    if password_file:
        values["LABADDA_SMTP_PASSWORD_FILE"] = password_file
    return values


def site_json(  # noqa: PLR0917 — one value per installer answer
    site: str,
    prefix: str,
    hostname: str,
    port: int,
    user: str,
    base_path: str = "",
    web_access: str = "https",
) -> dict:
    """The reviewed site description; every path sits under `prefix` (empty on a real server)."""
    shared = {"web_access": web_access} if web_access == "shared-http" else {}
    return shared | {
        "instance": site,
        "root": f"{prefix}/srv/labadda/{site}",
        "user": user,
        "group": user,
        "env_file": f"{prefix}/etc/labadda/{site}.env",
        "server_name": hostname,
        "port": port,
        "base_path": base_path,
        "tls_certificate": f"{prefix}/etc/ssl/labadda/server.crt",
        "tls_key": f"{prefix}/etc/ssl/labadda/server.key",
        "backup_root": f"{prefix}/srv/labadda-backups/{site}",
    }


def env_file(example: str, values: dict[str, str]) -> str:
    """Copy the example, replacing only the named settings; unknown names are an error."""
    seen: set[str] = set()
    lines = []
    for line in example.splitlines():
        key = line.partition("=")[0]
        if key in values and not line.startswith("#"):
            lines.append(f"{key}={values[key]}")
            seen.add(key)
        else:
            lines.append(line)
    missing = set(values) - seen
    if missing:
        raise InputError("Settings not in the example file: " + ", ".join(sorted(missing)))
    return "\n".join(lines) + "\n"


def env_values(
    site: str,
    root: str,
    port: int,
    hostname: str,
    *,
    zone: str,
    domain: str,
    db_url: str,
    base_path: str = "",
    web_access: str = "https",
) -> dict:
    # A shared plain-HTTP site cannot carry Secure cookies; the cookie path is still the prefix.
    shared = web_access == "shared-http"
    return {
        "LABADDA_ENV": "pilot",
        "LABADDA_INSTANCE": site,
        "LABADDA_PORT": str(port),
        "LABADDA_BASE_PATH": base_path,
        "LABADDA_DATABASE_URL": db_url,
        "LABADDA_COOKIE_NAME": f"labadda_{site}",
        "LABADDA_COOKIE_SECURE": "false" if shared else "true",
        "LABADDA_TRUSTED_ORIGINS": f"{'http' if shared else 'https'}://{hostname}",
        "LABADDA_ASSET_DIR": f"{root}/assets",
        "LABADDA_FRONTEND_DIST": f"{root}/current/frontend/dist",
        "LABADDA_TIMEZONE": zone,
        "LABADDA_STATUS_DIR": f"{root}/status",
        "LABADDA_EMAIL_DOMAIN": domain.lstrip("@"),
    }


def status_facts(status_dir: Path, now: datetime | None = None) -> dict:
    """Last backup as a sentence-ready record; unknown stays unknown, never healthy."""
    reading = backup_status.read_status(status_dir)
    if reading.state != "ok" or reading.status is None:
        return {"backup": reading.state, "age_hours": None}
    stamp = reading.status
    hours = backup_status.age(stamp, now or datetime.now(UTC)).total_seconds() / 3600
    return {
        "backup": stamp.result,
        "verification": stamp.verification,
        "finished_at": stamp.finished_at.strftime(backup_status.TIME_FORMAT),
        "age_hours": round(hours, 1),
        "size_bytes": stamp.size_bytes,
    }


def attach_site(site_file: Path, include: str, *, remove: bool = False) -> str:
    """Add or remove `include <file>;` inside the single server block of another application's site.

    Only this one line is ever written, so the other application's routes stay byte-for-byte the
    same; the caller keeps a backup and runs nginx -t before reloading."""
    text = site_file.read_text()
    marker = f"include {include};"
    lines = text.splitlines(keepends=True)
    if remove:
        kept = [line for line in lines if marker not in line]
        if len(kept) == len(lines):
            return "absent"
        _replace(site_file, "".join(kept))
        return "removed"
    if marker in text:
        return "present"
    blocks = len(SERVER_BLOCK.findall(text))
    if blocks != 1:
        raise InputError(
            f"{site_file} has {blocks} server blocks; add the line '{marker}' by hand inside the "
            "plain-HTTP one, then run the installer again."
        )
    closing = max(i for i, line in enumerate(lines) if line.strip())
    if lines[closing].strip() != "}":
        raise InputError(f"{site_file} does not end with the server block's closing brace.")
    lines.insert(closing, f"    {marker}  # LabAdda under its own path; added by the LabAdda installer\n")
    _replace(site_file, "".join(lines))
    return "added"


def _replace(path: Path, text: str) -> None:
    mode = path.stat().st_mode & 0o7777
    handle, temporary = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
    with os.fdopen(handle, "w") as stream:
        stream.write(text)
    os.chmod(temporary, mode)
    os.replace(temporary, path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    one = sub.add_parser("site-json")
    env = sub.add_parser("env-file")
    for p in (one, env):
        p.add_argument("--site", required=True)
        p.add_argument("--prefix", default="")
        p.add_argument("--hostname", required=True)
        p.add_argument("--port", type=int, required=True)
    one.add_argument("--user", required=True)
    for p in (one, env):
        p.add_argument("--base-path", default="")
        p.add_argument("--web-access", choices=WEB_ACCESS, default="https")
    env.add_argument("--example", type=Path, required=True)
    env.add_argument("--zone", required=True)
    env.add_argument("--domain", default="")
    env.add_argument("--database-url", required=True)
    for name in ("--feedback", "--smtp-relay", "--smtp-from", "--smtp-user", "--smtp-password-file"):
        env.add_argument(name, default="")
    env.add_argument("--smtp-starttls", action="store_true")
    env.add_argument("--run-scheduler", choices=("true", "false"), default="true")
    stat = sub.add_parser("status")
    stat.add_argument("--status-dir", type=Path, required=True)
    attach = sub.add_parser("attach-site")
    attach.add_argument("--site-file", type=Path, required=True)
    attach.add_argument("--include", required=True)
    attach.add_argument("--remove", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.command == "site-json":
            check_answers(args.site, args.hostname, "UTC", "")
            check_web(args.web_access, args.base_path)
            description = site_json(
                args.site, args.prefix, args.hostname, args.port, args.user, args.base_path, args.web_access
            )
            print(json.dumps(description, indent=2))
        elif args.command == "env-file":
            check_answers(args.site, args.hostname, args.zone, args.domain)
            check_web(args.web_access, args.base_path)
            root = f"{args.prefix}/srv/labadda/{args.site}"
            values = env_values(
                args.site,
                root,
                args.port,
                args.hostname,
                zone=args.zone,
                domain=args.domain,
                db_url=args.database_url,
                base_path=args.base_path,
                web_access=args.web_access,
            )
            values["LABADDA_RUN_SCHEDULER"] = args.run_scheduler
            values |= smtp_settings(
                args.smtp_relay, args.feedback, args.smtp_from,
                starttls=args.smtp_starttls, user=args.smtp_user, password_file=args.smtp_password_file,
            )  # fmt: skip
            sys.stdout.write(env_file(args.example.read_text(), values))
        elif args.command == "attach-site":
            print(attach_site(args.site_file, args.include, remove=args.remove))
        else:
            print(json.dumps(status_facts(args.status_dir)))
        return 0
    except (InputError, OSError) as error:
        print(f"{error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
