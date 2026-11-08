#!/usr/bin/env python3
"""Build and install verified, self-contained LabAdda releases.

Uses only the standard library. Trust the tool and the separately delivered digest
before processing an archive; hashes provide integrity, not publisher identity.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tarfile
import uuid
import tempfile
import venv
import zipfile
from email.parser import BytesParser
from pathlib import Path, PurePosixPath

FORMAT = 1
MAX_FILES = 10000
MAX_BYTES = 2 * 1024**3
RELEASE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,79}\Z")


class ReleaseError(Exception):
    """A candidate is unsafe or cannot be used on this host."""


def run(*args: str | Path, cwd: Path | None = None, env: dict | None = None) -> None:
    subprocess.run([str(a) for a in args], cwd=cwd, env=env, check=True)


def digest(path: Path) -> str:
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def host_platform() -> dict:
    distro = platform.freedesktop_os_release()
    return {"os": distro["ID"], "os_version": distro["VERSION_ID"],
            "machine": platform.machine(), "python": f"{sys.version_info.major}.{sys.version_info.minor}"}


def safe_path(value: str) -> bool:
    return (isinstance(value, str) and bool(value) and "\\" not in value
            and not any(ord(c) < 32 for c in value)
            and not value.startswith("/") and all(p not in ("", ".", "..") for p in value.split("/")))


def inventory(wheels: Path, licenses: Path) -> list[dict]:
    result = []
    for wheel in sorted(wheels.glob("*.whl")):
        with zipfile.ZipFile(wheel) as archive:
            metadata_names = [n for n in archive.namelist() if n.endswith(".dist-info/METADATA")]
            if len(metadata_names) != 1:
                raise ReleaseError(f"Invalid wheel metadata: {wheel.name}")
            metadata = BytesParser().parsebytes(archive.read(metadata_names[0]))
            license_files = []
            for name in archive.namelist():
                if archive.getinfo(name).is_dir():
                    continue
                if any(word in PurePosixPath(name).name.lower() for word in ("license", "copying", "notice")):
                    if not safe_path(name):
                        raise ReleaseError("Unsafe license path")
                    target = licenses / wheel.name / name
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(archive.read(name))
                    license_files.append(target.relative_to(licenses.parent).as_posix())
            result.append({"name": metadata["Name"], "version": metadata["Version"],
                           "wheel": wheel.name, "license": metadata.get("License-Expression") or metadata.get("License"),
                           "license_classifiers": metadata.get_all("Classifier", []), "license_files": license_files})
    return result


def frontend_inventory(root: Path, stage: Path) -> list[dict]:
    lock = json.loads((root / "frontend/package-lock.json").read_text())
    result = []
    for name, entry in sorted(lock["packages"].items()):
        if not name or entry.get("dev"):
            continue
        package = root / "frontend" / name
        metadata = json.loads((package / "package.json").read_text())
        texts = []
        for source in package.iterdir():
            if source.is_file() and any(word in source.name.lower() for word in ("license", "notice", "copying")):
                target = stage / "licenses/frontend" / name / source.name
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, target)
                texts.append(target.relative_to(stage).as_posix())
        result.append({"name": metadata["name"], "version": metadata["version"],
                       "license": metadata.get("license"), "license_files": texts,
                       "integrity": entry.get("integrity")})
    return result


def build(root: Path, output: Path, release_id: str) -> Path:
    if not RELEASE_ID.fullmatch(release_id):
        raise ReleaseError("Invalid release ID")
    if sys.version_info[:2] != (3, 12):
        raise ReleaseError("Build with Python 3.12")
    status = subprocess.check_output(["git", "status", "--porcelain", "--untracked-files=normal"], cwd=root)
    if status:
        raise ReleaseError("Build from a clean committed checkout")
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    output.mkdir(parents=True, exist_ok=True)
    archive_path = output / f"labadda-{release_id}.tar.gz"
    if archive_path.exists() or archive_path.with_suffix(".gz.sha256").exists():
        raise ReleaseError("Release output already exists")
    with tempfile.TemporaryDirectory() as temporary:
        stage = Path(temporary) / "payload"
        stage.mkdir()
        for name in ("backend", "frontend", "deploy", "docs", "scripts"):
            (stage / name).mkdir()
        # Copy only committed runtime source/config, never local state or credentials.
        paths = subprocess.check_output(["git", "ls-files", "-z"], cwd=root).decode().split("\0")
        for name in filter(None, paths):
            include = (name.startswith(("backend/labadda/", "backend/migrations/", "deploy/"))
                       or name in ("backend/alembic.ini", "backend/requirements.lock", "backend/pyproject.toml",
                                   "scripts/release.py", "docs/DEPLOYMENT.md", "docs/RELEASES.md", "docs/RECOVERY.md"))
            if include:
                source = root / name
                if source.is_symlink() or not source.is_file():
                    raise ReleaseError(f"Runtime source must be a regular file: {name}")
                target = stage / name
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, target)
        run("npm", "ci", cwd=root / "frontend")
        run("npm", "run", "build", cwd=root / "frontend")
        shutil.copytree(root / "frontend/dist", stage / "frontend/dist")
        wheels = stage / "wheelhouse"
        wheels.mkdir()
        run(sys.executable, "-m", "pip", "download", "--only-binary=:all:", "--dest", wheels,
            "-r", root / "backend/requirements.lock")
        dependencies = inventory(wheels, stage / "licenses")
        frontend_dependencies = frontend_inventory(root, stage)
        files = {p.relative_to(stage).as_posix(): {"sha256": digest(p), "size": p.stat().st_size}
                 for p in sorted(stage.rglob("*")) if p.is_file()}
        manifest = {"format": FORMAT, "release": release_id, "commit": commit,
                    "platform": host_platform(), "schema": subprocess.check_output([sys.executable, "-c", "from labadda.app import expected_schema_head; print(expected_schema_head())"], cwd=root / "backend", text=True).strip(), "files": files,
                    "dependencies": dependencies, "frontend_dependencies": frontend_dependencies}
        (stage / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
        with tarfile.open(archive_path, "w:gz") as archive:
            for path in sorted(stage.rglob("*")):
                if path.is_file():
                    archive.add(path, arcname=path.relative_to(stage).as_posix(), recursive=False)
    archive_path.with_suffix(".gz.sha256").write_text(f"{digest(archive_path)}  {archive_path.name}\n")
    return archive_path


def verify(archive_path: Path, expected_digest: str) -> dict:
    if not re.fullmatch(r"[0-9a-f]{64}", expected_digest) or digest(archive_path) != expected_digest:
        raise ReleaseError("Archive SHA-256 mismatch")
    with tarfile.open(archive_path, "r:gz") as archive:
        members = []
        total = 0
        for member in archive:
            members.append(member)
            total += member.size
            if len(members) > MAX_FILES or total > MAX_BYTES:
                raise ReleaseError("Archive exceeds release limits")
        names = set()
        for member in members:
            if not member.isfile() or not safe_path(member.name) or member.name in names or member.size < 0:
                raise ReleaseError("Unsafe, duplicate, or non-regular archive member")
            names.add(member.name)
        if "manifest.json" not in names or archive.getmember("manifest.json").size > 8 * 1024**2:
            raise ReleaseError("Missing or oversized manifest")
        manifest = json.load(archive.extractfile("manifest.json"))
        if manifest.get("format") != FORMAT or not RELEASE_ID.fullmatch(manifest.get("release", "")):
            raise ReleaseError("Unsupported manifest")
        if manifest.get("platform") != host_platform():
            raise ReleaseError("Release platform does not match this host")
        files = manifest.get("files", {})
        if set(files) != names - {"manifest.json"}:
            raise ReleaseError("Manifest does not cover archive exactly")
        required = {"backend/labadda/app.py", "backend/alembic.ini", "backend/requirements.lock",
                    "frontend/dist/index.html", "scripts/release.py", "docs/RELEASES.md"}
        if not required <= names or not any(n.startswith("wheelhouse/") and n.endswith(".whl") for n in names):
            raise ReleaseError("Incomplete release")
        for member in members:
            if member.name == "manifest.json":
                continue
            info = files[member.name]
            if member.size != info["size"] or hashlib.file_digest(archive.extractfile(member), "sha256").hexdigest() != info["sha256"]:
                raise ReleaseError(f"Payload hash mismatch: {member.name}")
        # Flat files cannot also be parents of other files.
        if any(str(parent) in names for name in names for parent in PurePosixPath(name).parents if str(parent) != "."):
            raise ReleaseError("Conflicting archive paths")
    return manifest


def install(archive_path: Path, expected_digest: str, instance: Path) -> Path:
    # A private snapshot binds verification and extraction to identical bytes even
    # when a transfer directory is concurrently replaced by another process.
    with tempfile.TemporaryDirectory() as temporary:
        snapshot = Path(temporary) / "candidate.tar.gz"
        shutil.copyfile(archive_path, snapshot)
        return install_snapshot(snapshot, expected_digest, instance)


def install_snapshot(archive_path: Path, expected_digest: str, instance: Path) -> Path:
    manifest = verify(archive_path, expected_digest)
    instance.mkdir(parents=True, exist_ok=True)
    releases = instance / "releases"
    releases.mkdir(exist_ok=True)
    target = releases / manifest["release"]
    if target.exists():
        raise ReleaseError("Release is already installed; use a new release ID")
    required_space = sum(f["size"] for f in manifest["files"].values()) * 3 + 256 * 1024**2
    if shutil.disk_usage(releases).free < required_space:
        raise ReleaseError("Insufficient free disk space")
    # Prepare at its final path: venv entry points embed absolute paths.
    target.mkdir()
    try:
        with tarfile.open(archive_path, "r:gz") as archive:
            # Recheck the digest before extracting; never use extractall or archive permissions.
            if digest(archive_path) != expected_digest:
                raise ReleaseError("Archive changed during installation")
            for member in archive.getmembers():
                destination = target / member.name
                destination.parent.mkdir(parents=True, exist_ok=True)
                with destination.open("xb") as sink:
                    shutil.copyfileobj(archive.extractfile(member), sink)
        venv.EnvBuilder(with_pip=True).create(target / "venv")
        python = target / "venv/bin/python"
        offline = {k: v for k, v in os.environ.items()
                   if not k.startswith(("PIP_", "PYTHON"))}
        offline.update(PIP_NO_INDEX="1", PIP_DISABLE_PIP_VERSION_CHECK="1", PIP_CONFIG_FILE=os.devnull)
        run(python, "-m", "pip", "install", "--no-index", "--only-binary=:all:", "--find-links", target / "wheelhouse",
            "-r", target / "backend/requirements.lock", env=offline)
        # Source layout retains migrations beside the package, as required by the CLI.
        site = subprocess.check_output([str(python), "-I", "-c", "import site; print(site.getsitepackages()[0])"], text=True, env=offline).strip()
        Path(site, "labadda.pth").write_text(str(target / "backend") + "\n")
        run(python, "-c", "import labadda.app, psycopg, PIL; from labadda.app import expected_schema_head; " + "\nif expected_schema_head() != " + repr(manifest["schema"]) + ": raise RuntimeError('Schema mismatch')", env=offline)
    except BaseException:
        shutil.rmtree(target)
        raise
    return target


def validate_installed(target: Path) -> dict:
    if target.is_symlink() or not target.is_dir():
        raise ReleaseError("Release must be a regular directory")
    manifest = json.loads((target / "manifest.json").read_text())
    for name, info in manifest["files"].items():
        if not safe_path(name):
            raise ReleaseError("Unsafe installed payload path")
        path = target / name
        if not path.resolve().is_relative_to(target.resolve()) or path.is_symlink() or digest(path) != info["sha256"]:
            raise ReleaseError(f"Installed payload changed: {name}")
    return manifest


def preflight(instance: Path, release_id: str) -> str:
    """Read actual runtime settings and database state without exposing secrets."""
    if not RELEASE_ID.fullmatch(release_id):
        raise ReleaseError("Invalid release ID")
    target = instance / "releases" / release_id
    validate_installed(target)
    code = r"""
import os
from pathlib import Path
from sqlalchemy import create_engine, text
from labadda.config import load_settings
s = load_settings()
def require(condition, message):
    if not condition:
        raise ValueError(message)
require(s.environment in ('staging', 'pilot'), 'Set LABADDA_ENV to staging or pilot')
require(s.instance and s.instance != 'dev', 'Set a distinct instance name')
require(s.cookie_name != 'labadda_session', 'Set a distinct instance cookie')
require(s.cookie_secure and s.trusted_origins, 'Configure TLS cookies and trusted origins')
require(all(o.startswith('https://') for o in s.trusted_origins), 'Trusted origins must use HTTPS')
assets = s.asset_dir.resolve()
require(s.asset_dir.is_absolute() and assets.is_dir() and os.access(assets, os.W_OK), 'Configure writable absolute asset directory')
require(not assets.is_relative_to(Path.cwd().resolve().parent), 'Assets must be outside all releases')
with create_engine(s.database_url, connect_args={'connect_timeout': 10}).connect() as db:
    rows = db.execute(text('select version_num from alembic_version')).scalars().all()
    require(len(rows) == 1, 'Expected one schema head')
    print(rows[0])
"""
    runtime_env = {k: v for k, v in os.environ.items() if not k.startswith("PYTHON")}
    result = subprocess.run([str(target / "venv/bin/python"), "-I", "-c", code], cwd=target,
                            text=True, capture_output=True, env=runtime_env)
    if result.returncode:
        # SQLAlchemy exceptions can contain connection details. Do not relay stderr.
        raise ReleaseError("Runtime preflight failed: check instance/TLS/cookie/assets settings and database/schema access; connection details suppressed")
    schema = result.stdout.strip()
    if not re.fullmatch(r"[A-Za-z0-9_]+", schema):
        raise ReleaseError("Invalid observed schema")
    return schema


def switch(instance: Path, release_id: str, schema: str, *, rollback: bool = False) -> None:
    """Switch code only; callers quiesce writers, migrate, restart, and probe."""
    if not RELEASE_ID.fullmatch(release_id):
        raise ReleaseError("Invalid release ID")
    target = instance / "releases" / release_id
    manifest = json.loads((target / "manifest.json").read_text())
    if manifest["schema"] != schema:
        raise ReleaseError("Schema mismatch: hold maintenance; do not rewind data")
    current = instance / "current"
    if current.exists() and not current.is_symlink():
        raise ReleaseError("Current release must be a symlink")
    if rollback and not current.is_symlink():
        raise ReleaseError("No active release to roll back")
    validate_installed(target)
    temporary = instance / (".current-next-" + uuid.uuid4().hex)
    try:
        temporary.symlink_to(Path("releases") / release_id)
        os.replace(temporary, current)
    finally:
        temporary.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    builder = commands.add_parser("build")
    builder.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    builder.add_argument("--output", type=Path, required=True)
    builder.add_argument("--release", required=True)
    for name in ("verify", "install"):
        sub = commands.add_parser(name)
        sub.add_argument("archive", type=Path)
        sub.add_argument("--sha256", required=True, help="digest from a separately trusted channel")
        if name == "install":
            sub.add_argument("--instance", type=Path, required=True)
    for name in ("preflight", "activate", "rollback"):
        sub = commands.add_parser(name)
        sub.add_argument("--instance", type=Path, required=True)
        sub.add_argument("--release", required=True)
        if name != "preflight":
            sub.add_argument("--database-schema", required=True, help="expected observed alembic_version after migration")
            sub.add_argument("--writers-quiesced", action="store_true", required=True)
            sub.add_argument("--backup-verified", action="store_true", required=True)
    args = parser.parse_args()
    try:
        if args.command == "build":
            print(build(args.root.resolve(), args.output.resolve(), args.release))
        elif args.command == "verify":
            print(json.dumps(verify(args.archive, args.sha256), indent=2))
        elif args.command == "install":
            print(install(args.archive.resolve(), args.sha256, args.instance.resolve()))
        elif args.command == "preflight":
            print("Observed database schema:", preflight(args.instance.resolve(), args.release))
        else:
            schema = preflight(args.instance.resolve(), args.release)
            if schema != args.database_schema:
                raise ReleaseError("Observed database schema differs from operator expectation")
            switch(args.instance.resolve(), args.release, schema, rollback=args.command == "rollback")
            print("Pointer switched. Restart and run the documented readiness and functional probes before serving traffic.")
        return 0
    except (ReleaseError, OSError, ValueError, KeyError, tarfile.TarError, subprocess.CalledProcessError) as exc:
        print(f"release: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
