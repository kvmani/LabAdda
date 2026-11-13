"""Offline kit builder/verifier and the install helpers (no database, no root, no network)."""

import hashlib
import io
import json
import subprocess
import sys
import tarfile
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
DEPLOY = SCRIPTS.parent / "deploy"
sys.path.insert(0, str(SCRIPTS))
import install_helpers  # noqa: E402
import kit  # noqa: E402
import operations  # noqa: E402
import site_environment  # noqa: E402


def fake_root(tmp_path, version="9.9.9-test"):
    root = tmp_path / "src"
    (root / "backend/labadda").mkdir(parents=True)
    (root / "backend/labadda/__init__.py").write_text(f'"""x."""\n\n__version__ = "{version}"\n')
    (root / "deploy/lib").mkdir(parents=True)
    for name in kit.LAUNCHERS:
        (root / "deploy" / name).write_text("#!/bin/bash\n")
    (root / "deploy/lib/common.sh").write_text("# lib\n")
    (root / "deploy/os-packages.txt").write_text("nginx  # web\n\n")
    (root / "docs").mkdir()
    (root / "docs/ROLLOUT-INTRANET.md").write_text("# Guide\n")
    return root


def fake_archive(tmp_path, version="9.9.9-test"):
    members = {f"scripts/{n}": b"# tool" for n in kit.TOOL_SCRIPTS}
    members.update(dict.fromkeys(kit.TOOL_BACKEND, b"# backend"))
    members["deploy/labadda.env.example"] = b"A=1\n"
    members["wheelhouse/x.whl"] = b"w"
    manifest = {"release": version, "commit": "c" * 40, "schema": "0001", "platform": {}}
    members["manifest.json"] = json.dumps(manifest).encode()
    path = tmp_path / f"labadda-{version}.tar.gz"
    with tarfile.open(path, "w:gz") as tar:
        for name, data in members.items():
            info = tarfile.TarInfo(name)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
    path.with_suffix(".gz.sha256").write_text(
        f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}\n"
    )
    return path


def run(*args, **kwargs):
    return subprocess.run(args, check=False, capture_output=True, **kwargs)  # noqa: S603


@pytest.fixture
def built(tmp_path):
    root = fake_root(tmp_path)
    return kit.build(tmp_path / "out", root=root, archive=fake_archive(tmp_path), skip_debs=True)


def test_version_comes_from_the_code_and_names_the_kit(tmp_path):
    root = fake_root(tmp_path, "0.0.1-beta")
    assert kit.code_version(root) == "0.0.1-beta"
    assert kit.kit_name("0.0.1-beta") == "labadda-0.0.1-beta-offline-kit"
    (root / kit.VERSION_FILE).write_text("nothing here\n")
    with pytest.raises(kit.KitError):
        kit.code_version(root)


def test_real_repository_has_a_usable_version():
    assert kit.code_version()


def test_package_list_ignores_comments():
    assert {"postgresql-16", "nginx", "python3.12-venv"} <= set(kit.package_names())
    assert not any(n.startswith("#") or " " in n for n in kit.package_names())


def test_built_kit_verifies_and_lists_every_file(built):
    assert kit.check(built, allow_no_debs=True, deep=False) == []
    sums = (built / "SHA256SUMS").read_text().splitlines()
    assert all(len(line.split("  ")[0]) == 64 for line in sums)
    names = {line.split("  ")[1] for line in sums}
    assert {"install.sh", "lib/common.sh", "READ-ME-FIRST.md", "tools/scripts/lifecycle.py"} <= names
    assert any(n.startswith("release/") and n.endswith(".tar.gz") for n in names)
    checked = run("sha256sum", "--quiet", "-c", "SHA256SUMS", cwd=built)
    assert checked.returncode == 0


def test_verify_catches_damage_extras_and_missing_files(built):
    (built / "install.sh").write_text("#!/bin/bash\necho tampered\n")
    assert any(
        "changed or damaged: install.sh" in p for p in kit.check(built, allow_no_debs=True, deep=False)
    )
    (built / "extra.txt").write_text("x")
    assert any(
        "not in the manifest: extra.txt" in p for p in kit.check(built, allow_no_debs=True, deep=False)
    )
    (built / "lib/common.sh").unlink()
    assert any("missing: lib/common.sh" in p for p in kit.check(built, allow_no_debs=True, deep=False))


def test_kit_without_os_packages_is_not_complete(built):
    assert any("os-packages" in p for p in kit.check(built, deep=False))


def test_build_refuses_to_overwrite_and_cleans_up(tmp_path):
    root = fake_root(tmp_path)
    archive = fake_archive(tmp_path)
    kit.build(tmp_path / "out", root=root, archive=archive, skip_debs=True)
    with pytest.raises(kit.KitError):
        kit.build(tmp_path / "out", root=root, archive=archive, skip_debs=True)
    (root / "deploy/status.sh").unlink()
    broken = tmp_path / "out2"
    with pytest.raises(OSError):
        kit.build(broken, root=root, archive=archive, skip_debs=True)
    assert not any(p.name.startswith(".") for p in broken.iterdir())


def test_missing_tool_in_archive_is_refused(tmp_path):
    root = fake_root(tmp_path)
    with tarfile.open(tmp_path / "bad.tar.gz", "w:gz"):
        pass
    with pytest.raises(kit.KitError):
        kit.extract_tools(tmp_path / "bad.tar.gz", tmp_path / "t")
    assert root.exists()


def test_every_kit_script_is_valid_bash():
    for path in [*DEPLOY.glob("*.sh"), *DEPLOY.glob("lib/*.sh"), SCRIPTS / "make-offline-kit.sh"]:
        assert run("bash", "-n", str(path)).returncode == 0, path
    for name in kit.LAUNCHERS:
        assert (DEPLOY / name).stat().st_mode & 0o111, f"{name} must be executable"


def test_launchers_name_no_literal_version():
    for path in DEPLOY.glob("*.sh"):
        assert kit.code_version() not in path.read_text(), path.name


def test_site_json_is_accepted_by_the_reviewed_site_loader(tmp_path):
    data = install_helpers.site_json("main", "/srv/rehearsal", "labadda.lab.example.in", 8100, "labadda")
    path = tmp_path / "main.site.json"
    path.write_text(json.dumps(data))
    site = operations.load_site(path)
    assert site["root"] == "/srv/rehearsal/srv/labadda/main"
    assert site["base_path"] == ""


def test_env_file_passes_the_runtime_environment_check(tmp_path):
    site = install_helpers.site_json("main", "", "labadda.lab.example.in", 8100, "labadda")
    values = install_helpers.env_values(
        "main", site["root"], 8100, "labadda.lab.example.in", zone="Asia/Kolkata", domain="@lab.example.in",
        db_url="postgresql+psycopg://labadda_main:secret@localhost:5432/labadda_main",
    )  # fmt: skip
    text = install_helpers.env_file((DEPLOY / "labadda.env.example").read_text(), values)
    env_path = tmp_path / "main.env"
    env_path.write_text(text)
    env_path.chmod(0o600)
    environment = site_environment.runtime_environment({**site, "env_file": str(env_path)})
    assert environment["LABADDA_ENV"] == "pilot"
    assert environment["LABADDA_TIMEZONE"] == "Asia/Kolkata"
    assert environment["LABADDA_EMAIL_DOMAIN"] == "lab.example.in"
    assert text.count("LABADDA_DATABASE_URL=") == 1


def test_env_file_rejects_unknown_setting():
    with pytest.raises(install_helpers.InputError):
        install_helpers.env_file("A=1\n", {"B": "2"})


@pytest.mark.parametrize(
    "args",
    [("Main", "h.example.in", "Asia/Kolkata", ""), ("main", "bad host", "Asia/Kolkata", ""),
     ("main", "h.example.in", "not a zone", ""), ("main", "h.example.in", "UTC", "a b"),
     ("main", "h.example.in", "UTC", "", "nobody")],
)  # fmt: skip
def test_answers_that_cannot_be_used_are_refused(args):
    with pytest.raises(install_helpers.InputError):
        install_helpers.check_answers(*args)


def test_backup_status_unknown_is_not_reported_as_healthy(tmp_path):
    assert install_helpers.status_facts(tmp_path) == {"backup": "unknown", "age_hours": None}


def test_backup_unit_can_import_its_sibling_modules(tmp_path):
    unit = (DEPLOY / "systemd/labadda-backup@.service").read_text()
    flags = unit.split("ExecStart=")[1].split()[1:3]
    assert flags == ["-E", "-s"]
    done = run(sys.executable, *flags, str(SCRIPTS / "lifecycle.py"), "--help", cwd=tmp_path)
    assert done.returncode == 0, done.stderr
