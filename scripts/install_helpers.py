#!/usr/bin/env python3
"""Small, testable helpers for the on-server install scripts (standard library only).

install_helpers.py site-json ...   print the site description lifecycle.py and operations.py read
install_helpers.py env-file ...    print the private settings file from deploy/labadda.env.example
install_helpers.py status ...      print the one-screen summary facts as JSON
"""

from __future__ import annotations

import argparse
import json
import re
import sys
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


SMTP_HOST = re.compile(r"[a-z0-9]+(?:[.-][a-z0-9]+)*\Z")


class InputError(ValueError):
    """An answer that cannot be used, phrased for the person typing it."""


def check_answers(site: str, hostname: str, zone: str, domain: str, feedback: str = "") -> None:
    if not SITE.fullmatch(site):
        raise InputError("Site name: 1-20 lowercase letters or digits, starting with a letter.")
    if not HOST.fullmatch(hostname) or len(hostname) > 253:
        raise InputError("Server hostname: lowercase letters, digits, dots and hyphens only.")
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


def site_json(site: str, prefix: str, hostname: str, port: int, user: str) -> dict:
    """The reviewed site description; every path sits under `prefix` (empty on a real server)."""
    return {
        "instance": site,
        "root": f"{prefix}/srv/labadda/{site}",
        "user": user,
        "group": user,
        "env_file": f"{prefix}/etc/labadda/{site}.env",
        "server_name": hostname,
        "port": port,
        "base_path": "",
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
    site: str, root: str, port: int, hostname: str, *, zone: str, domain: str, db_url: str
) -> dict:
    return {
        "LABADDA_ENV": "pilot",
        "LABADDA_INSTANCE": site,
        "LABADDA_PORT": str(port),
        "LABADDA_BASE_PATH": "",
        "LABADDA_DATABASE_URL": db_url,
        "LABADDA_COOKIE_NAME": f"labadda_{site}",
        "LABADDA_COOKIE_SECURE": "true",
        "LABADDA_TRUSTED_ORIGINS": f"https://{hostname}",
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
    env.add_argument("--example", type=Path, required=True)
    env.add_argument("--zone", required=True)
    env.add_argument("--domain", default="")
    env.add_argument("--database-url", required=True)
    for name in ("--feedback", "--smtp-relay", "--smtp-from", "--smtp-user", "--smtp-password-file"):
        env.add_argument(name, default="")
    env.add_argument("--smtp-starttls", action="store_true")
    stat = sub.add_parser("status")
    stat.add_argument("--status-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "site-json":
            check_answers(args.site, args.hostname, "UTC", "")
            print(
                json.dumps(site_json(args.site, args.prefix, args.hostname, args.port, args.user), indent=2)
            )
        elif args.command == "env-file":
            check_answers(args.site, args.hostname, args.zone, args.domain)
            root = f"{args.prefix}/srv/labadda/{args.site}"
            values = env_values(
                args.site,
                root,
                args.port,
                args.hostname,
                zone=args.zone,
                domain=args.domain,
                db_url=args.database_url,
            )
            values |= smtp_settings(
                args.smtp_relay, args.feedback, args.smtp_from,
                starttls=args.smtp_starttls, user=args.smtp_user, password_file=args.smtp_password_file,
            )  # fmt: skip
            sys.stdout.write(env_file(args.example.read_text(), values))
        else:
            print(json.dumps(status_facts(args.status_dir)))
        return 0
    except (InputError, OSError) as error:
        print(f"{error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
