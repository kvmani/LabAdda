#!/usr/bin/env python3
"""Read a GitHub release "Source code (zip)" without git (standard library only).

GitHub makes the zip with `git archive`: the archive comment is the full commit SHA and every
entry carries the commit time. That is the build identity on a server that has no git checkout.
"""

from __future__ import annotations

import re
import zipfile
from pathlib import Path, PurePosixPath

COMMIT = re.compile(r"[0-9a-f]{40}\Z")
# Local state a copied-over folder may contain; a fresh zip never does, so it is never shipped.
SKIPPED_PARTS = {".git", "node_modules", ".venv", "__pycache__", "var"}


class SourceZipError(Exception):
    """The file is not a usable LabAdda source archive."""


def identity(archive: Path) -> tuple[str, str]:
    """(commit, commit date YYYY-MM-DD) recorded in the zip by git archive."""
    with zipfile.ZipFile(archive) as bundle:
        commit = bundle.comment.decode("ascii", "replace").strip()
        if not COMMIT.fullmatch(commit):
            raise SourceZipError("The zip carries no commit; use GitHub's 'Source code (zip)' of a release")
        newest = max((info.date_time for info in bundle.infolist()), default=None)
    if newest is None:
        raise SourceZipError("The zip is empty")
    return commit, f"{newest[0]:04d}-{newest[1]:02d}-{newest[2]:02d}"


def extract(archive: Path, destination: Path) -> Path:
    """Extract into an empty folder and return the source root (the zip's single top folder)."""
    destination.mkdir(parents=True, exist_ok=False)
    with zipfile.ZipFile(archive) as bundle:
        tops = set()
        for info in bundle.infolist():
            name = PurePosixPath(info.filename)
            if name.is_absolute() or ".." in name.parts or info.external_attr >> 16 & 0o170000 == 0o120000:
                raise SourceZipError(f"Unsafe entry in the zip: {info.filename}")
            tops.add(name.parts[0])
        if len(tops) != 1:
            raise SourceZipError("The zip must hold exactly one top folder")
        bundle.extractall(destination)
    root = destination / tops.pop()
    if not (root / "backend/labadda/__init__.py").is_file():
        raise SourceZipError("This zip is not a LabAdda source archive")
    return root


def tree_files(root: Path) -> list[str]:
    """Every regular file of an extracted source tree, as git ls-files would list it."""
    names = []
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root)
        if path.is_file() and not path.is_symlink() and not SKIPPED_PARTS & set(relative.parts):
            names.append(relative.as_posix())
    return names


def main(argv: list[str] | None = None) -> int:
    import argparse  # noqa: PLC0415 — the command line is only for the on-server shell scripts
    import sys  # noqa: PLC0415

    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("identity").add_argument("zip", type=Path)
    unpack = sub.add_parser("extract")
    unpack.add_argument("zip", type=Path)
    unpack.add_argument("destination", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == "identity":
            print(" ".join(identity(args.zip)))
        else:
            print(extract(args.zip, args.destination))
        return 0
    except (SourceZipError, OSError, zipfile.BadZipFile) as error:
        print(f"source zip: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
