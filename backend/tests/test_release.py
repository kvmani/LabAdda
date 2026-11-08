"""T12 archive validation and activation failure paths (no database required)."""
import importlib.util
import io
import json
import hashlib
import tarfile
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location("release", Path(__file__).resolve().parents[2] / "scripts/release.py")
release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release)


def candidate(tmp_path, *, extra=None, change=None, member_type=None):
    files = {name: b"fixture" for name in (
        "backend/labadda/app.py", "backend/alembic.ini", "backend/requirements.lock",
        "frontend/dist/index.html", "scripts/release.py", "docs/RELEASES.md", "wheelhouse/example.whl")}
    manifest = {"format": 1, "release": "candidate", "platform": release.host_platform(), "schema": "0005",
                "files": {n: {"size": len(b), "sha256": hashlib.sha256(b).hexdigest()} for n, b in files.items()}}
    if change:
        change(manifest)
    files["manifest.json"] = json.dumps(manifest).encode()
    archive = tmp_path / "candidate.tar.gz"
    with tarfile.open(archive, "w:gz") as tar:
        for name, data in files.items():
            info = tarfile.TarInfo(name)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
        if extra:
            info = tarfile.TarInfo(extra)
            if member_type:
                info.type = member_type
                info.linkname = "/etc/passwd"
            tar.addfile(info, io.BytesIO(b""))
    return archive, release.digest(archive)


def test_valid_archive(tmp_path):
    archive, sha = candidate(tmp_path)
    assert release.verify(archive, sha)["release"] == "candidate"


@pytest.mark.parametrize("name", ["../escape", "/absolute", "a/../escape", "a//b", "a/./b", "a\\b", "manifest.json"])
def test_unsafe_or_duplicate_members(tmp_path, name):
    archive, sha = candidate(tmp_path, extra=name)
    with pytest.raises(release.ReleaseError):
        release.verify(archive, sha)


@pytest.mark.parametrize("kind", [tarfile.SYMTYPE, tarfile.LNKTYPE, tarfile.DIRTYPE, tarfile.FIFOTYPE])
def test_non_regular_members(tmp_path, kind):
    archive, sha = candidate(tmp_path, extra="link", member_type=kind)
    with pytest.raises(release.ReleaseError):
        release.verify(archive, sha)


def test_wrong_outer_digest(tmp_path):
    archive, _ = candidate(tmp_path)
    with pytest.raises(release.ReleaseError, match="SHA-256"):
        release.verify(archive, "0" * 64)


@pytest.mark.parametrize("change", [
    lambda m: m["platform"].update(machine="other"),
    lambda m: m["files"].pop("frontend/dist/index.html"),
    lambda m: m["files"]["frontend/dist/index.html"].update(sha256="0" * 64),
    lambda m: m.update(format=99),
    lambda m: m.update(release="../bad"),
])
def test_invalid_manifest(tmp_path, change):
    archive, sha = candidate(tmp_path, change=change)
    with pytest.raises(release.ReleaseError):
        release.verify(archive, sha)


def installed(tmp_path, name, schema="0005"):
    target = tmp_path / "releases" / name
    target.mkdir(parents=True)
    (target / "payload").write_text("original")
    (target / "manifest.json").write_text(json.dumps({"schema": schema, "files": {
        "payload": {"sha256": release.digest(target / "payload"), "size": 8}}}))
    return target


def test_activate_and_rollback_preserve_state(tmp_path):
    installed(tmp_path, "previous")
    installed(tmp_path, "candidate")
    state = tmp_path / "assets"
    state.mkdir()
    (state / "existing").write_text("keep")
    release.switch(tmp_path, "previous", "0005")
    release.switch(tmp_path, "candidate", "0005")
    assert (tmp_path / "current").resolve().name == "candidate"
    release.switch(tmp_path, "previous", "0005", rollback=True)
    assert (tmp_path / "current").resolve().name == "previous"
    assert (state / "existing").read_text() == "keep"


def test_schema_mismatch_leaves_current_untouched(tmp_path):
    installed(tmp_path, "previous")
    installed(tmp_path, "candidate", "0006")
    release.switch(tmp_path, "previous", "0005")
    with pytest.raises(release.ReleaseError, match="Schema mismatch"):
        release.switch(tmp_path, "candidate", "0005")
    assert (tmp_path / "current").resolve().name == "previous"


def test_tampered_candidate_leaves_current_untouched(tmp_path):
    installed(tmp_path, "previous")
    target = installed(tmp_path, "candidate")
    release.switch(tmp_path, "previous", "0005")
    (target / "payload").write_text("changed")
    with pytest.raises(release.ReleaseError, match="payload changed"):
        release.switch(tmp_path, "candidate", "0005")
    assert (tmp_path / "current").resolve().name == "previous"


def test_install_failure_removes_only_new_candidate(tmp_path, monkeypatch):
    archive, sha = candidate(tmp_path)
    instance = tmp_path / "instance"
    installed(instance, "previous")
    monkeypatch.setattr(release.venv.EnvBuilder, "create", lambda *a: (_ for _ in ()).throw(OSError("disk failed")))
    with pytest.raises(OSError, match="disk failed"):
        release.install(archive, sha, instance)
    assert not (instance / "releases/candidate").exists()
    assert (instance / "releases/previous/payload").read_text() == "original"


def test_transfer_replacement_cannot_change_verified_snapshot(tmp_path, monkeypatch):
    archive, sha = candidate(tmp_path)
    original = archive.read_bytes()
    def inspect_snapshot(snapshot, expected, instance):
        archive.write_bytes(b"concurrently replaced transfer")
        assert snapshot != archive
        assert snapshot.read_bytes() == original
        assert release.verify(snapshot, expected)["release"] == "candidate"
        return instance
    monkeypatch.setattr(release, "install_snapshot", inspect_snapshot)
    assert release.install(archive, sha, tmp_path / "instance") == tmp_path / "instance"


def test_preflight_refuses_tampering_before_executing_candidate(tmp_path, monkeypatch):
    target = installed(tmp_path, "candidate")
    (target / "payload").write_text("tampered")
    def must_not_run(*args, **kwargs):
        pytest.fail("tampered candidate must never execute")
    monkeypatch.setattr(release.subprocess, "run", must_not_run)
    with pytest.raises(release.ReleaseError, match="payload changed"):
        release.preflight(tmp_path, "candidate")


def test_preflight_checks_survive_optimization(tmp_path, monkeypatch):
    import sys
    target = installed(tmp_path, "candidate")
    (target / "venv").symlink_to(sys.prefix, target_is_directory=True)
    real_run = release.subprocess.run
    def optimized_run(command, **kwargs):
        result = real_run([command[0], "-O", *command[1:]], **kwargs)
        assert "Set LABADDA_ENV to staging or pilot" in result.stderr
        assert "ModuleNotFoundError" not in result.stderr
        return result
    monkeypatch.setattr(release.subprocess, "run", optimized_run)
    monkeypatch.setenv("PYTHONOPTIMIZE", "1")
    monkeypatch.setenv("LABADDA_ENV", "development")
    monkeypatch.setenv("LABADDA_ASSET_DIR", "/does-not-exist")
    with pytest.raises(release.ReleaseError, match="preflight failed"):
        release.preflight(tmp_path, "candidate")


def test_activation_temporary_link_does_not_clobber_other_operation(tmp_path, monkeypatch):
    installed(tmp_path, "candidate")
    other = tmp_path / ".current-next-other"
    other.symlink_to("other-release")
    release.switch(tmp_path, "candidate", "0005")
    assert other.is_symlink()


def test_archive_resource_limit(tmp_path, monkeypatch):
    archive, sha = candidate(tmp_path)
    monkeypatch.setattr(release, "MAX_FILES", 2)
    with pytest.raises(release.ReleaseError, match="limits"):
        release.verify(archive, sha)


def test_offline_install_scrubs_ambient_package_sources(tmp_path, monkeypatch):
    archive, sha = candidate(tmp_path)
    monkeypatch.setenv("PIP_FIND_LINKS", "https://untrusted.example/wheels")
    monkeypatch.setenv("PYTHONPATH", "/untrusted")
    monkeypatch.setattr(release.venv.EnvBuilder, "create", lambda *args: None)
    def inspect_pip(*args, **kwargs):
        env = kwargs["env"]
        assert "PIP_FIND_LINKS" not in env
        assert "PYTHONPATH" not in env
        assert env["PIP_NO_INDEX"] == "1"
        assert env["PIP_CONFIG_FILE"] == release.os.devnull
        raise RuntimeError("checked isolated pip")
    monkeypatch.setattr(release, "run", inspect_pip)
    with pytest.raises(RuntimeError, match="checked isolated pip"):
        release.install(archive, sha, tmp_path / "instance")
    assert not (tmp_path / "instance/releases/candidate").exists()


def test_wheel_inventory_handles_license_directories(tmp_path):
    import zipfile
    wheels = tmp_path / "wheelhouse"
    wheels.mkdir()
    with zipfile.ZipFile(wheels / "example.whl", "w") as archive:
        archive.writestr("example-1.dist-info/METADATA", "Name: example\nVersion: 1\nLicense-Expression: MIT\n")
        archive.mkdir("example-1.dist-info/licenses/")
        archive.writestr("example-1.dist-info/licenses/LICENSE", "Example license")
    inventory = release.inventory(wheels, tmp_path / "licenses")
    assert inventory[0]["license"] == "MIT"
    assert len(inventory[0]["license_files"]) == 1
    assert (tmp_path / inventory[0]["license_files"][0]).read_text() == "Example license"
