from pathlib import Path

import pytest

from labadda.recovery import RecoveryError, copy_assets, inventory, verify_bundle, write_manifest


def bundle(tmp_path):
    root = tmp_path / 'bundle'
    root.mkdir()
    (root / 'assets').mkdir()
    (root / 'assets/file.bin').write_bytes(b'synthetic content')
    (root / 'database.dump').write_bytes(b'fixture dump')
    write_manifest(root, schema='0005', release='fixture', recovery_point='2026-11-08T00:00:00Z')
    return root


def test_bundle_integrity_and_permissions(tmp_path):
    root = bundle(tmp_path)
    assert verify_bundle(root)['schema'] == '0005'
    assert root.stat().st_mode & 0o777 == 0o700
    assert (root / 'database.dump').stat().st_mode & 0o777 == 0o600


@pytest.mark.parametrize('mutation', ['alter', 'missing', 'extra', 'link'])
def test_payload_changes_refused(tmp_path, mutation):
    root = bundle(tmp_path)
    path = root / 'assets/file.bin'
    if mutation == 'alter':
        path.write_text('changed')
    elif mutation == 'missing':
        path.unlink()
    elif mutation == 'extra':
        (root / 'extra').write_text('unexpected')
    else:
        path.unlink()
        path.symlink_to('/etc/passwd')
    with pytest.raises(RecoveryError):
        verify_bundle(root)


def test_copy_preserves_nested_asset_hashes(tmp_path):
    source = tmp_path / 'source'
    (source / 'nested').mkdir(parents=True)
    (source / 'nested/file').write_bytes(b'bytes')
    assert copy_assets(source, tmp_path / 'copy') == inventory(source)


def test_symlink_directory_refused(tmp_path):
    (tmp_path / 'link').symlink_to('/tmp', target_is_directory=True)
    with pytest.raises(RecoveryError):
        inventory(tmp_path)


def test_backup_requires_quiescence_before_access(tmp_path):
    from labadda.recovery import backup
    with pytest.raises(RecoveryError, match='Stop app'):
        backup('unused', tmp_path, tmp_path / 'backup', 'fixture', writers_quiesced=False)


def test_libpq_connection_environment_excludes_stale_selectors(monkeypatch):
    from labadda.recovery import postgres_environment
    monkeypatch.setenv('PGSERVICE', 'unrelated')
    monkeypatch.setenv('PGSSLMODE', 'verify-full')
    with pytest.raises(RecoveryError, match='ambient'):
        postgres_environment('postgresql+psycopg://fixture:fixture@localhost:5432/fixture')
    monkeypatch.delenv('PGSERVICE')
    env = postgres_environment('postgresql+psycopg://fixture:fixture@localhost:5432/fixture')
    assert 'PGSERVICE' not in env
    assert env['PGSSLMODE'] == 'verify-full'
    assert env['PGDATABASE'] == 'fixture'


def test_failed_dump_leaves_no_published_backup(tmp_path, migrated, monkeypatch):
    from labadda import recovery
    assets = tmp_path / 'assets'
    assets.mkdir()
    def failed(*args):
        raise RecoveryError('injected dump failure')
    monkeypatch.setattr(recovery, 'pg_command', failed)
    target = tmp_path / 'backup'
    with pytest.raises(RecoveryError, match='injected'):
        recovery.backup(migrated, assets, target, 'fixture', writers_quiesced=True)
    assert not target.exists()
    assert not list(tmp_path.glob('.recovery-*'))


def test_restore_requires_isolation_before_access(tmp_path):
    from labadda.recovery import restore
    with pytest.raises(RecoveryError, match='isolated'):
        restore(tmp_path, 'unused', 'unused', tmp_path / 'assets', isolated_target=False)


def test_restore_refuses_wrong_manifest_digest_before_database_access(tmp_path):
    from labadda.recovery import restore
    root = bundle(tmp_path)
    with pytest.raises(RecoveryError, match='digest'):
        restore(root, '0' * 64, 'unused', tmp_path / 'assets', isolated_target=True)


def test_restore_does_not_overwrite_assets(tmp_path):
    from labadda.recovery import restore, file_hash
    root = bundle(tmp_path)
    assets = tmp_path / 'assets'
    assets.mkdir()
    with pytest.raises(RecoveryError, match='must not exist'):
        restore(root, file_hash(root / 'manifest.json'), 'unused', assets, isolated_target=True)


def test_restore_cli_requires_explicit_target(monkeypatch, capsys):
    from labadda.cli import main
    monkeypatch.delenv('LABADDA_RESTORE_DATABASE_URL', raising=False)
    assert main(['restore', 'unused', '--manifest-sha256', '0'*64, '--isolated-target']) == 2
    assert 'LABADDA_RESTORE_DATABASE_URL' in capsys.readouterr().err


def test_restore_refuses_asset_overlap_without_modifying_bundle(tmp_path):
    from labadda.recovery import restore, file_hash
    root = bundle(tmp_path)
    before = inventory(root)
    with pytest.raises(RecoveryError, match='separate'):
        restore(root, file_hash(root / 'manifest.json'), 'unused', root / 'nested/assets', isolated_target=True)
    assert inventory(root) == before


@pytest.mark.parametrize('url', ['postgresql:///fixture', 'postgresql://user:pass@localhost/fixture'])
def test_implicit_connection_selectors_refused(url):
    from labadda.recovery import postgres_environment
    with pytest.raises(RecoveryError, match='explicit'):
        postgres_environment(url)
