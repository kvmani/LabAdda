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
