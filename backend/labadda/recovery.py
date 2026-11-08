"""Verified recovery bundles. Recovery roots must be private, operator-owned paths."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
from pathlib import Path


class RecoveryError(Exception):
    pass


def file_hash(path: Path) -> str:
    with path.open('rb') as source:
        return hashlib.file_digest(source, 'sha256').hexdigest()


def inventory(root: Path) -> dict:
    if root.is_symlink() or not root.is_dir():
        raise RecoveryError('Expected a regular directory')
    result = {}
    for directory, dirs, files in os.walk(root, followlinks=False):
        for name in dirs + files:
            path = Path(directory) / name
            if path.is_symlink() or not (path.is_file() or path.is_dir()):
                raise RecoveryError('Links and special files are forbidden')
        for name in files:
            path = Path(directory) / name
            result[path.relative_to(root).as_posix()] = {'size': path.stat().st_size, 'sha256': file_hash(path)}
    return result


def copy_assets(source: Path, target: Path) -> dict:
    before = inventory(source)
    shutil.copytree(source, target)
    copied = inventory(target)
    if before != copied or before != inventory(source):
        raise RecoveryError('Assets changed during snapshot; keep writers stopped and retry')
    return copied


def verify_bundle(root: Path) -> dict:
    actual = inventory(root)
    manifest = json.loads((root / 'manifest.json').read_text())
    if manifest.get('format') != 1 or not isinstance(manifest.get('files'), dict):
        raise RecoveryError('Unsupported recovery manifest')
    actual.pop('manifest.json', None)
    if actual != manifest['files']:
        raise RecoveryError('Recovery payload does not match manifest')
    if 'database.dump' not in actual or not isinstance(manifest.get('schema'), str):
        raise RecoveryError('Incomplete recovery bundle')
    return manifest


def write_manifest(root: Path, *, schema: str, release: str, recovery_point: str) -> None:
    manifest = {'format': 1, 'schema': schema, 'release': release,
                'recovery_point': recovery_point, 'files': inventory(root)}
    (root / 'manifest.json').write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n')
    for directory, _, files in os.walk(root):
        Path(directory).chmod(0o700)
        for name in files:
            (Path(directory) / name).chmod(0o600)


def postgres_environment(url: str) -> dict:
    from sqlalchemy.engine import make_url
    parsed = make_url(url)
    if parsed.get_backend_name() != 'postgresql' or parsed.query:
        raise RecoveryError('Use a PostgreSQL URL without query options; configure TLS through PGSSL*')
    env = {k: v for k, v in os.environ.items() if not k.startswith('PG')}
    # Retain explicit libpq TLS configuration, never a stale connection selector.
    env.update({k: v for k, v in os.environ.items() if k.startswith('PGSSL')})
    env.update(PGHOST=parsed.host or 'localhost', PGPORT=str(parsed.port or 5432),
               PGUSER=parsed.username or '', PGPASSWORD=parsed.password or '', PGDATABASE=parsed.database or '',
               PGCONNECT_TIMEOUT='10')
    return env


def pg_command(program: str, url: str, *args: str | Path) -> None:
    import subprocess
    try:
        subprocess.run([program, *map(str, args)], env=postgres_environment(url),
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    except (OSError, subprocess.CalledProcessError) as exc:
        raise RecoveryError(f'{Path(program).name} failed; check PostgreSQL client version and access (details suppressed)') from exc


def sync_tree(root: Path) -> None:
    for directory, _, files in os.walk(root, topdown=False):
        for name in files:
            with (Path(directory) / name).open('rb') as stream:
                os.fsync(stream.fileno())
        fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)


def backup(url: str, assets: Path, destination: Path, release: str, *, writers_quiesced: bool,
           pg_dump: str = 'pg_dump') -> str:
    from datetime import datetime, timezone
    from sqlalchemy import create_engine, inspect, text
    if not writers_quiesced:
        raise RecoveryError('Stop app, sockets, scheduler and CLI writers before backup')
    assets = assets.absolute()
    destination = destination.absolute()
    if destination.exists() or destination.is_symlink():
        raise RecoveryError('Backup destination already exists')
    if destination.resolve().is_relative_to(assets.resolve()) or assets.resolve().is_relative_to(destination.resolve()):
        raise RecoveryError('Backup and asset roots must be separate')
    destination.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(url, connect_args={'connect_timeout': 10})
    try:
        with tempfile.TemporaryDirectory(prefix='.recovery-', dir=destination.parent) as temporary:
            stage = Path(temporary) / 'bundle'
            stage.mkdir(mode=0o700)
            with engine.begin() as conn:
                conn.execute(text("SET LOCAL lock_timeout = '10s'"))
                names = inspect(conn).get_table_names(schema='public')
                if 'alembic_version' not in names:
                    raise RecoveryError('Source is not a migrated LabAdda database')
                quote = conn.dialect.identifier_preparer.quote
                tables = ', '.join('public.' + quote(name) for name in sorted(names))
                conn.execute(text('LOCK TABLE ' + tables + ' IN SHARE MODE'))
                schemas = conn.execute(text('select version_num from alembic_version')).scalars().all()
                if len(schemas) != 1:
                    raise RecoveryError('Expected one schema head')
                point = datetime.now(timezone.utc).isoformat()
                pg_command(pg_dump, url, '--format=custom', '--no-owner', '--no-acl', '--file', stage / 'database.dump')
                copy_assets(assets, stage / 'assets')
                write_manifest(stage, schema=schemas[0], release=release, recovery_point=point)
                manifest = json.loads((stage / 'manifest.json').read_text())
                manifest['source_database'] = engine.url.database
                (stage / 'manifest.json').write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n')
                verify_bundle(stage)
                sync_tree(stage)
                os.rename(stage, destination)
            fd = os.open(destination.parent, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(fd)
            finally:
                os.close(fd)
        return file_hash(destination / 'manifest.json')
    finally:
        engine.dispose()
