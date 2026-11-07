"""Operator and developer commands: ``labadda <command>``."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from alembic import command
from alembic.config import Config

from .config import load_settings
from .db import session_factory

ROOT = Path(__file__).resolve().parents[1]


def alembic_config(url: str) -> Config:
    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(ROOT / "migrations"))
    cfg.attributes["database_url"] = url
    return cfg


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="labadda")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("migrate", help="apply schema migrations to head")
    seed = sub.add_parser("seed", help="load the fictional fixture (development/test only)")
    seed.add_argument("--reset", action="store_true", help="erase all data first")
    serve = sub.add_parser("serve", help="run the ASGI server on loopback")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8000)
    admin = sub.add_parser("create-admin", help="create an administrator and print a one-time activation token")
    admin.add_argument("username")
    admin.add_argument("--display-name", default=None)
    sub.add_parser("reminders", help="process due reminders once")
    args = parser.parse_args(argv)
    settings = load_settings()

    if args.cmd == "migrate":
        command.upgrade(alembic_config(settings.database_url), "head")
        return 0
    if args.cmd == "seed":
        if not settings.fixtures_allowed:
            print("Refusing to load fixtures: LABADDA_ENV must be development or test.", file=sys.stderr)
            return 2
        from .fixtures import reset_database, seed as run_seed

        with session_factory(settings.database_url)() as db:
            if args.reset:
                reset_database(db)
            print(json.dumps(run_seed(db), indent=2))
        return 0
    if args.cmd == "serve":
        import uvicorn

        logging.basicConfig(level=logging.INFO, format="%(message)s")
        uvicorn.run("labadda.app:create_app", factory=True, host=args.host, port=args.port, proxy_headers=True,
                    forwarded_allow_ips="127.0.0.1", ws_max_size=64 * 1024)
        return 0
    if args.cmd == "create-admin":
        from sqlalchemy import select

        from .api.auth import issue_credential
        from .models import User

        with session_factory(settings.database_url)() as db:
            username = args.username.strip().lower()
            if db.scalar(select(User).where(User.username == username)):
                print("That username already exists.", file=sys.stderr)
                return 1
            user = User(username=username, display_name=args.display_name or username, is_admin=True)
            db.add(user)
            db.flush()
            token, cred = issue_credential(db, user, "activation", None, settings)
            db.commit()
            print(f"Activation token for {username} (expires {cred.expires_at.isoformat()}):")
            print(token)
            print("Open <base>/activate and enter this token. Do not store it in logs.")
        return 0
    if args.cmd == "reminders":
        from .scheduler import process_due_reminders

        with session_factory(settings.database_url)() as db:
            print(f"created {process_due_reminders(db)} notifications")
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
