"""Shared-server shell regressions use scratch paths and never touch host services."""

import json
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def shell(tmp_path, script):
    import pytest

    if not Path("/bin/bash").exists():
        pytest.skip("/bin/bash is required for deployment shell tests")
    return subprocess.run(  # noqa: S603 — fixed repository shell scripts and synthetic scratch paths only
        ["/bin/bash", "-c", script],
        env={**os.environ, "LABADDA_ROOT_PREFIX": str(tmp_path), "LABADDA_PYTHON312": "python3"},
        text=True,
        capture_output=True,
        check=False,
    )


def helpers():
    return f'source "{ROOT}/deploy/lib/common.sh"\nsource "{ROOT}/deploy/lib/steps.sh"\nset_paths\n'


def test_install_preserves_existing_default_nginx_site(tmp_path):
    default = tmp_path / "etc/nginx/sites-enabled/default"
    default.parent.mkdir(parents=True)
    default.write_text("existing project-management site")
    result = shell(
        tmp_path,
        helpers()
        + f'''
TOOLS_DIR="{ROOT}"
SYSTEMCTL=true
NO_NGINX=0
nginx() {{ return 0; }}
# Exercise the installer as an unprivileged pytest process. The owner itself is
# checked in the host rehearsal. Here keep the file operations and nginx assertions real.
install() {{
  local args=()
  while (($#)); do
    case $1 in -o|-g) shift 2 ;; *) args+=("$1"); shift ;; esac
  done
  command install "${{args[@]}}"
}}
operations() {{ mkdir -p "$3"; touch "$3/service.conf" "$3/nginx.conf"; }}
step_render_units
''',
    )
    assert result.returncode == 0, result.stderr
    assert default.read_text() == "existing project-management site"
    assert (tmp_path / "etc/nginx/conf.d/labadda-main.conf").exists()


def test_failed_restore_never_removes_retained_assets(tmp_path):
    marker = tmp_path / "srv/labadda/main/assets/retained.png"
    marker.parent.mkdir(parents=True)
    marker.write_bytes(b"synthetic retained image")
    result = shell(
        tmp_path,
        helpers()
        + """
RESTORE_BUNDLE=/unused
VERSION=candidate
RESTORE_SHA=unused
with_env() { return 1; }
step_initialize
""",
    )
    assert result.returncode != 0
    assert marker.read_bytes() == b"synthetic retained image"
    assert "refuses nonempty assets" in result.stderr


def test_restore_cleanup_requires_matching_disposable_provenance(tmp_path):
    site = tmp_path / "etc/labadda/second.site.json"
    site.parent.mkdir(parents=True)
    site.write_text(json.dumps({"root": str(tmp_path / "srv/labadda/second")}))
    result = shell(
        tmp_path, f'bash "{ROOT}/deploy/restore.sh" --dry-run --remove-test --site main --test-site second'
    )
    assert result.returncode != 0
    assert "provenance" in result.stderr
    assert site.exists()
    result = shell(tmp_path, f'bash "{ROOT}/deploy/restore.sh" --dry-run --remove-test --test-site ../main')
    assert result.returncode != 0


def test_release_id_collision_refuses_a_different_commit(tmp_path):
    installed, candidate = tmp_path / "installed.json", tmp_path / "candidate.json"
    installed.write_text(json.dumps({"commit": "a" * 40}))
    candidate.write_text(json.dumps({"commit": "b" * 40}))
    result = shell(tmp_path, helpers() + f'assert_release_identity "{installed}" "{candidate}"')
    assert result.returncode != 0
    assert "Release ID collision" in result.stderr
    candidate.write_text(installed.read_text())
    result = shell(tmp_path, helpers() + f'assert_release_identity "{installed}" "{candidate}"')
    assert result.returncode == 0


def test_disposable_restore_disables_copied_mail_and_background_jobs(tmp_path):
    kit = tmp_path / "kit"
    (kit / "lib").mkdir(parents=True)
    (kit / "restore.sh").write_text((ROOT / "deploy/restore.sh").read_text())
    (kit / "lib/common.sh").write_text((ROOT / "deploy/lib/common.sh").read_text())
    (kit / "install.sh").write_text("""#!/bin/bash
set -eu
while (($#)); do
  if [[ $1 == --answers ]]; then cat "$2"; exit 0; fi
  shift
done
exit 1
""")
    answers = tmp_path / "etc/labadda/main.install.conf"
    answers.parent.mkdir(parents=True)
    answers.write_text(
        "FEEDBACK_EMAIL=operators@domain.xx.in\nSMTP_RELAY=relay.domain.xx.in:25\n"
        "SMTP_USER=relayuser\nRUN_SCHEDULER=true\nSERVICE_USER=labadda\nHOSTNAME_=labadda.domain.xx.in\n"
    )
    bundle = tmp_path / "synthetic-backup"
    bundle.mkdir()
    result = shell(
        tmp_path, f'bash "{kit}/restore.sh" --dry-run --bundle "{bundle}" --manifest-sha256 {"a" * 64}'
    )
    assert result.returncode == 0, result.stderr
    assert "FEEDBACK_EMAIL=none" in result.stdout
    assert "SMTP_RELAY=none" in result.stdout
    assert "SMTP_USER=none" in result.stdout
    assert "RUN_SCHEDULER=false" in result.stdout
    assert "SERVICE_USER=labadda-mainrestore" in result.stdout
    assert "operators@domain.xx.in" not in result.stdout
    assert "relay.domain.xx.in" not in result.stdout
    # A user-scope site's copy runs under the same account, still without mail or background jobs.
    answers.write_text(answers.read_text() + "SERVICE_SCOPE=user\n")
    result = shell(
        tmp_path, f'bash "{kit}/restore.sh" --dry-run --bundle "{bundle}" --manifest-sha256 {"a" * 64}'
    )
    assert result.returncode == 0, result.stderr
    assert "SERVICE_USER=labadda\n" in result.stdout
    assert "labadda-mainrestore" not in result.stdout
    assert "RUN_SCHEDULER=false" in result.stdout
    assert "relay.domain.xx.in" not in result.stdout


def test_failed_shared_attachment_restores_existing_nginx_files(tmp_path):
    base = tmp_path / "etc/nginx"
    target = base / "sites-enabled/pm"
    snippet = base / "snippets/labadda-main.conf"
    mapping = base / "conf.d/labadda-main.conf"
    original = f"server {{\n    include {snippet};\n}}\n"
    for path, content in ((target, original), (snippet, "old route\n"), (mapping, "old map\n")):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
    result = shell(
        tmp_path,
        helpers()
        + f'''
TOOLS_DIR="{ROOT}"
SHARED_SITE=/etc/nginx/sites-enabled/pm
mkdir -p "$ETC_DIR" "$PREFIX/rendered"
echo new-route >"$PREFIX/rendered/locations.conf"
echo new-map >"$PREFIX/rendered/nginx.conf"
nginx() {{ return 1; }}
attach_shared_site "$PREFIX/rendered"
''',
    )
    assert result.returncode != 0
    assert "prior files were restored" in result.stderr
    assert target.read_text() == original
    assert snippet.read_text() == "old route\n"
    assert mapping.read_text() == "old map\n"


def test_isolated_restore_only_requires_direct_readiness(tmp_path):
    result = shell(
        tmp_path,
        helpers()
        + """
NO_NGINX=1
RESTORE_BUNDLE=/synthetic-backup
lifecycle() { return 1; }
step_backup_and_doctor
""",
    )
    assert result.returncode == 0, result.stderr
    assert "direct readiness confirmed" in result.stdout


def test_site_environment_is_validated_and_never_sourced(tmp_path):
    etc = tmp_path / "etc/labadda"
    etc.mkdir(parents=True)
    site = json.loads((ROOT / "deploy/site.example.json").read_text())
    env_file = etc / "main.env"
    site["env_file"] = str(env_file)
    (etc / "main.site.json").write_text(json.dumps(site))
    values = {
        "INSTANCE": site["instance"],
        "PORT": site["port"],
        "ENV": "pilot",
        "BASE_PATH": site["base_path"],
        "ASSET_DIR": site["root"] + "/assets",
        "FRONTEND_DIST": site["root"] + "/current/frontend/dist",
        "COOKIE_NAME": "labadda_example",
        "COOKIE_SECURE": "true",
        "TRUSTED_ORIGINS": "https://" + site["server_name"],
        "DATABASE_URL": "postgresql+psycopg://labadda:example@127.0.0.1/labadda",
    }
    payload = "".join(f"LABADDA_{key}={value}\n" for key, value in values.items())
    env_file.write_text(payload)
    env_file.chmod(0o600)
    command = helpers() + f'TOOLS_DIR="{ROOT}"\nwith_env printenv LABADDA_BASE_PATH'
    result = shell(tmp_path, command)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == site["base_path"]
    marker = tmp_path / "unexpected"
    env_file.write_text(payload + f"touch {marker}\n")
    result = shell(tmp_path, command)
    assert result.returncode != 0
    assert not marker.exists()
