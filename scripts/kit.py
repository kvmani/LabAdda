#!/usr/bin/env python3
"""Build and check the offline install kit: everything a pilot server needs, on one USB drive.

The kit wraps the release archive made by `release.py` (application, built frontend, Python
wheelhouse) with what a blank Ubuntu 24.04 server still needs without internet: its operating
system packages as a small local package repository, the operator scripts and the install guide.
Every file is listed with its SHA-256 in `MANIFEST.json` and `SHA256SUMS`. Standard library only.

    kit.py build --output DIR          run on a connected Ubuntu 24.04 x86-64 build machine
    kit.py verify DIR                  run on the build machine and again on the server
    kit.py version                     print the application version (the single source)
"""

from __future__ import annotations

import argparse
import gzip
import json
import re
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path

import release

ROOT = Path(__file__).resolve().parents[1]
FORMAT = 1
VERSION_FILE = "backend/labadda/__init__.py"
PACKAGE_LIST = "deploy/os-packages.txt"
APT_CLOSURE = "--recurse --no-recommends --no-suggests --no-conflicts --no-breaks --no-replaces --no-enhances"
# Scripts the kit puts at its top level; they are copied from deploy/ in the same commit.
LAUNCHERS = ("install.sh", "upgrade.sh", "status.sh", "backup-now.sh", "restore.sh", "uninstall-keep-data.sh")
# Operator tools copied out of the release archive so the server never runs unverified code.
TOOL_SCRIPTS = (
    "release.py",
    "lifecycle.py",
    "commission.py",
    "operations.py",
    "backup_tools.py",
    "site_environment.py",
    "site_state.py",
    "install_helpers.py",
    "kit.py",
)
TOOL_BACKEND = ("backend/labadda/__init__.py", "backend/labadda/backup_status.py")


class KitError(Exception):
    """The kit cannot be built or does not match its manifest."""


def code_version(root: Path = ROOT) -> str:
    """Read the version from the code's single source; never from a literal in a script."""
    match = re.search(r'^__version__\s*=\s*"([^"]+)"', (root / VERSION_FILE).read_text(), re.M)
    if not match or not release.RELEASE_ID.fullmatch(match[1]):
        raise KitError(f"No usable __version__ in {VERSION_FILE}")
    return match[1]


def kit_name(version: str) -> str:
    return f"labadda-{version}-offline-kit"


def package_names(root: Path = ROOT) -> list[str]:
    lines = (root / PACKAGE_LIST).read_text().splitlines()
    names = [line.split("#")[0].strip() for line in lines]
    return [n for n in names if n]


def apt(*args: str) -> str:
    return subprocess.run(["apt-cache", *args], capture_output=True, text=True, check=True).stdout


def package_closure(names: list[str]) -> list[str]:
    """Every package the named ones need, so the server can install them with no index."""
    out = apt("depends", *APT_CLOSURE.split(), *names)
    wanted = {line.strip() for line in out.splitlines() if re.match(r"[a-z0-9]", line)}
    found = []
    for name in sorted(wanted):
        policy = apt("policy", name)
        if "Candidate: (none)" not in policy and "Candidate:" in policy:
            found.append(name)  # virtual packages have no candidate and need no file
    missing = [n for n in names if n not in found]
    if missing:
        raise KitError(f"Not available from this machine's package sources: {', '.join(missing)}")
    return found


def fetch_debs(names: list[str], target: Path) -> None:
    target.mkdir(parents=True)
    subprocess.run(["apt-get", "download", *names], cwd=target, check=True)
    if not list(target.glob("*.deb")):
        raise KitError("No operating system packages were downloaded")
    scan = subprocess.run(["dpkg-scanpackages", "--multiversion", ".", "/dev/null"], cwd=target,
                          capture_output=True, check=True)  # fmt: skip
    (target / "Packages").write_bytes(scan.stdout)
    (target / "Packages.gz").write_bytes(gzip.compress(scan.stdout, mtime=0))
    (target / "requested-packages.txt").write_text("\n".join(package_names()) + "\n")


def extract_tools(archive: Path, target: Path) -> None:
    """Copy the operator tools from the verified release archive, byte for byte."""
    wanted = {f"scripts/{n}": f"scripts/{n}" for n in TOOL_SCRIPTS}
    wanted.update({n: n for n in TOOL_BACKEND})
    with tarfile.open(archive, "r:gz") as tar:
        names = {m.name for m in tar.getmembers()}
        for name in tar.getmembers():
            if name.name.startswith("deploy/"):
                wanted[name.name] = name.name
        missing = sorted(set(wanted) - names)
        if missing:
            raise KitError(f"Release archive lacks operator files: {', '.join(missing)}")
        for source, dest in wanted.items():
            out = target / dest
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_bytes(tar.extractfile(source).read())
            out.chmod(0o755 if dest.endswith((".sh", ".py")) else 0o644)


def inventory(kit: Path) -> dict[str, dict]:
    return {
        p.relative_to(kit).as_posix(): {"sha256": release.digest(p), "size": p.stat().st_size}
        for p in sorted(kit.rglob("*"))
        if p.is_file() and p.name not in ("MANIFEST.json", "SHA256SUMS")
    }


def write_manifest(kit: Path, version: str, release_manifest: dict) -> None:
    files = inventory(kit)
    manifest = {
        "format": FORMAT,
        "kit": kit_name(version),
        "version": version,
        "release": release_manifest["release"],
        "commit": release_manifest["commit"],
        "schema": release_manifest["schema"],
        "platform": release_manifest["platform"],
        "files": files,
    }
    (kit / "MANIFEST.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    sums = "".join(f"{info['sha256']}  {name}\n" for name, info in files.items())
    (kit / "SHA256SUMS").write_text(sums)


def build(output: Path, *, root: Path = ROOT, archive: Path | None = None, skip_debs: bool = False) -> Path:
    version = code_version(root)
    kit = output / kit_name(version)
    if kit.exists():
        raise KitError(f"{kit} already exists; choose another output folder or remove it")
    work = output / f".{kit_name(version)}.partial"
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    try:
        if archive is None:
            archive = release.build(root, work / "build", version)
        digest_file = archive.with_suffix(".gz.sha256")
        (work / "release").mkdir()
        for source in (archive, digest_file):
            shutil.copyfile(source, work / "release" / source.name)
        extract_tools(archive, work / "tools")
        for name in LAUNCHERS:
            shutil.copyfile(root / "deploy" / name, work / name)
            (work / name).chmod(0o755)
        shutil.copytree(root / "deploy/lib", work / "lib")
        shutil.copyfile(root / "docs/ROLLOUT-INTRANET.md", work / "READ-ME-FIRST.md")
        if not skip_debs:
            fetch_debs(package_closure(package_names(root)), work / "os-packages")
        shutil.rmtree(work / "build", ignore_errors=True)
        with tarfile.open(work / "release" / archive.name, "r:gz") as tar:
            release_manifest = json.load(tar.extractfile("manifest.json"))
        write_manifest(work, version, release_manifest)
        problems = check(work, deep=False, allow_no_debs=skip_debs)
        if problems:
            raise KitError("; ".join(problems))
        work.rename(kit)
    except BaseException:
        shutil.rmtree(work, ignore_errors=True)
        raise
    return kit


def check(kit: Path, *, deep: bool = True, allow_no_debs: bool = False) -> list[str]:
    """Return what is wrong with a kit; an empty list means every file matches its manifest."""
    try:
        manifest = json.loads((kit / "MANIFEST.json").read_text())
    except (OSError, ValueError):
        return ["MANIFEST.json is missing or unreadable"]
    problems = []
    if manifest.get("format") != FORMAT or not isinstance(manifest.get("files"), dict):
        return ["MANIFEST.json is not a kit manifest of this format"]
    files = manifest["files"]
    present = {p.relative_to(kit).as_posix() for p in kit.rglob("*") if p.is_file()}
    present -= {"MANIFEST.json", "SHA256SUMS"}
    problems += [f"missing: {n}" for n in sorted(set(files) - present)]
    problems += [f"not in the manifest: {n}" for n in sorted(present - set(files))]
    for name in sorted(set(files) & present):
        if not release.safe_path(name) or release.digest(kit / name) != files[name]["sha256"]:
            problems.append(f"changed or damaged: {name}")
    version = manifest.get("version", "")
    archive = kit / "release" / f"labadda-{version}.tar.gz"
    if not archive.is_file():
        problems.append("the release archive is missing")
    elif not problems and deep:
        try:
            release.verify(archive, release.digest(archive))
        except release.ReleaseError as error:
            problems.append(f"release archive: {error}")
    if not allow_no_debs and not (kit / "os-packages/Packages.gz").is_file():
        problems.append("no operating system packages (os-packages/Packages.gz)")
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("version")
    built = sub.add_parser("build")
    built.add_argument("--output", type=Path, required=True)
    built.add_argument("--root", type=Path, default=ROOT)
    built.add_argument("--release-archive", type=Path, help="reuse an archive made by release.py")
    built.add_argument("--skip-os-packages", action="store_true", help="rehearsal only: no .deb files")
    check_cmd = sub.add_parser("verify")
    check_cmd.add_argument("kit", type=Path)
    check_cmd.add_argument("--no-deep", action="store_true", help="skip re-reading the archive contents")
    args = parser.parse_args(argv)
    try:
        if args.command == "version":
            print(code_version())
        elif args.command == "build":
            archive = args.release_archive.resolve() if args.release_archive else None
            kit = build(args.output.resolve(), root=args.root.resolve(), archive=archive,
                        skip_debs=args.skip_os_packages)  # fmt: skip
            print(kit)
        else:
            problems = check(args.kit.resolve(), deep=not args.no_deep)
            for problem in problems:
                print(f"PROBLEM  {problem}")
            print("kit verify: OK" if not problems else "kit verify: FAILED")
            return 1 if problems else 0
        return 0
    except (KitError, release.ReleaseError, OSError, subprocess.CalledProcessError) as error:
        print(f"kit: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
