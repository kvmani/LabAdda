"""Command-line options for maintenance, backup retention and compatible upgrade recovery."""

import argparse
from pathlib import Path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--site", type=Path, required=True)
    parser.add_argument("action", choices=("backup", "upgrade", "prune-backups"))
    parser.add_argument("--expected-current")
    parser.add_argument("--expected-schema")
    parser.add_argument("--candidate")
    parser.add_argument(
        "--recover-compatible",
        action="store_true",
        help="restore compatible code under the upgrade lock",
    )
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--external-writers-stopped", action="store_true")
    parser.add_argument(
        "--unattended",
        action="store_true",
        help="backup only: take the expected release and schema from the installed site (timer use)",
    )
    parser.add_argument(
        "--resume-after-backup",
        action="store_true",
        help="backup only: after a verified backup restart the service and lift maintenance",
    )
    parser.add_argument(
        "--destination-alias",
        default="local",
        help="short name shown for the backup location",
    )
    parser.add_argument("--keep", type=int, help="prune-backups only: how many finished backups to keep")
    return parser


def parse_args(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.recover_compatible and args.action != "upgrade":
        parser.error("--recover-compatible requires upgrade")
    if args.action == "prune-backups":
        if args.keep is None:
            parser.error("prune-backups requires --keep")
    elif args.action == "upgrade" and (args.unattended or args.resume_after_backup):
        parser.error("--unattended and --resume-after-backup apply to backup only")
    elif not args.unattended and not (args.expected_current and args.expected_schema):
        parser.error("--expected-current and --expected-schema are required unless --unattended")
    return args
