"""Site automation input boundaries and bounded readiness evidence."""

import importlib.util
import json
from pathlib import Path
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("operations", ROOT / "scripts/operations.py")
ops = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ops)


def site(tmp_path, **changes):
    value = json.loads((ROOT / "deploy/site.example.json").read_text())
    value.update(changes)
    path = tmp_path / "site.json"
    path.write_text(json.dumps(value))
    return path


@pytest.mark.parametrize(
    "change",
    [
        {"root": "/srv/../etc"},
        {"root": "/srv//labadda"},
        {"root": "/srv/labadda;id"},
        {"root": "/"},
        {"root": "/home/operator/site"},
        {"root": "/tmp/site"},
        {"tls_key": "/srv/labadda-backups/staging/key"},
        {"user": "root"},
        {"group": "root"},
        {"instance": "x\nExecStart=bad"},
        {"port": True},
        {"port": 80},
        {"port": 65536},
        {"base_path": "/x/../y"},
        {"base_path": "/x/"},
        {"server_name": "x;return 200"},
        {"server_name": "*.example"},
        {"backup_root": "/srv/labadda/staging/backup"},
        {"backup_root": "/srv"},
        {"env_file": "/srv/labadda/staging/secrets"},
        {"tls_key": "/etc/labadda/staging.env"},
        {"unexpected": "ignored"},
    ],
)
def test_reject_unsafe_configuration(tmp_path, change):
    with pytest.raises(ops.OperationsError):
        ops.load_site(site(tmp_path, **change))


def test_duplicate_keys_refused(tmp_path):
    path = tmp_path / "site.json"
    path.write_text('{"instance":"one", "instance":"two"}')
    with pytest.raises(ops.OperationsError, match="Duplicate"):
        ops.load_site(path)


@pytest.mark.parametrize("prefix", ["", "/labadda-staging", "/division/lab"])
def test_render_prefix_and_maintenance(tmp_path, prefix):
    config = ops.load_site(site(tmp_path, base_path=prefix))
    files = ops.render(config)
    assert f"location {prefix}/assets/" in files["nginx.conf"]
    assert "if (-f /srv/labadda/staging/traffic/maintenance) { return 503; }" in files["nginx.conf"]
    assert "KillMode=control-group" in files["service.conf"]
    assert "ProtectSystem=strict" in files["service.conf"]
    assert "ReadWritePaths=/srv/labadda/staging/assets" in files["service.conf"]
    assert "current/venv/bin/python -I -m labadda.cli" in files["service.conf"]
    out = tmp_path / "review"
    assert ops.main(["--site", str(tmp_path / "site.json"), "render", "--out", str(out)]) == 0
    assert ops.main(["--site", str(tmp_path / "site.json"), "render", "--out", str(out)]) == 1


class Response:
    status = 200

    def __init__(self, body):
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def read(self, limit):
        return self.body[:limit]


def test_probe_requires_exact_payload_and_no_redirect(tmp_path):
    config = ops.load_site(site(tmp_path))
    with patch.object(ops.urllib.request, "build_opener") as factory:
        opener = factory.return_value
        opener.open.side_effect = [Response(b'{"status":"ok"}'), Response(b'{"status":"wrong"}')]
        assert not ops.probe(config, direct=True)["passed"]
        assert opener.open.call_args.args[0] == "http://127.0.0.1:8102/labadda-staging/readyz"
        assert opener.open.call_args.kwargs["timeout"] == 10
    assert ops.NoRedirect().redirect_request(None, None, 302, "", {}, "https://other") is None
