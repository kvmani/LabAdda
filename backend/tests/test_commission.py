"""First-install/isolated-recovery sequencing; live target refusal and closed traffic."""

import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

pytest.importorskip("fcntl")

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import commission


@pytest.fixture
def target(tmp_path):
    root = tmp_path / "isolated"
    root.mkdir()
    (root / "traffic").mkdir()
    (root / "assets").mkdir()
    candidate = root / "releases/candidate"
    candidate.mkdir(parents=True)
    return {"root": str(root), "instance": "staging"}, root, candidate


@pytest.mark.parametrize("failure", ["service", "database", "migrate", "schema", "unloaded", None])
def test_initialize_never_starts_or_opens_traffic(target, failure):
    site, root, _candidate = target

    def command(args, **kwargs):
        assert args[1] == "show"
        if failure == "unloaded":
            return "LoadState=not-found\nMainPID=0\nActiveState=inactive"
        return (
            "LoadState=loaded\nMainPID=12\nActiveState=active"
            if failure == "service"
            else "LoadState=loaded\nMainPID=0\nActiveState=inactive"
        )

    with (
        patch.object(commission.release, "validate_installed", return_value={"schema": "0025"}),
        patch.object(commission.lifecycle, "runtime_environment", return_value={}),
        patch.object(commission.lifecycle, "command", side_effect=command),
        patch.object(commission, "empty_database") as empty,
        patch.object(commission.lifecycle, "cli") as cli,
        patch.object(commission.lifecycle, "schema", return_value="wrong" if failure == "schema" else "0025"),
    ):
        if failure == "database":
            empty.side_effect = commission.operations.OperationsError("not empty")
        if failure == "migrate":
            cli.side_effect = commission.operations.OperationsError("migrate failed")
        if failure:
            with pytest.raises(commission.operations.OperationsError):
                commission.prepare(site, "candidate", "initialize", apply=True, isolated_target=True)
        else:
            result = commission.prepare(site, "candidate", "initialize", apply=True, isolated_target=True)
            assert result["applied"] and not result["traffic_opened"]
        assert (root / "traffic/maintenance").exists()
        assert not (root / "current").exists()
        if failure in ("service", "database", "unloaded"):
            cli.assert_not_called()
        last = json.loads(next((root / "operations").glob("*.jsonl")).read_text().splitlines()[-1])
        assert last["event"] == ("failed" if failure else "completed_isolated")


def test_live_instance_refused_before_mutation(target):
    site, root, _candidate = target
    (root / "current").symlink_to("releases/candidate")
    with (
        patch.object(commission.release, "validate_installed"),
        patch.object(commission.lifecycle, "runtime_environment", return_value={}),
        pytest.raises(commission.operations.OperationsError, match="without a current"),
    ):
        commission.prepare(site, "candidate", "initialize")
    assert not (root / "operations").exists()


def test_restore_requires_absent_assets_and_trusted_digest(target, tmp_path):
    site, _root, _candidate = target
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    (bundle / "manifest.json").write_text("{}")
    with (
        patch.object(commission.release, "validate_installed"),
        patch.object(commission.lifecycle, "runtime_environment", return_value={}),
    ):
        with pytest.raises(commission.operations.OperationsError, match="trusted manifest"):
            commission.prepare(site, "candidate", "restore", bundle=bundle, manifest_sha256="0" * 64)
        with pytest.raises(commission.operations.OperationsError, match="absent"):
            commission.prepare(
                site,
                "candidate",
                "restore",
                bundle=bundle,
                manifest_sha256=commission.release.digest(bundle / "manifest.json"),
            )


def test_plan_never_checks_database_or_creates_state(target):
    site, root, _candidate = target
    with (
        patch.object(commission.release, "validate_installed"),
        patch.object(commission.lifecycle, "runtime_environment", return_value={}),
        patch.object(commission, "empty_database") as empty,
    ):
        result = commission.prepare(site, "candidate", "initialize")
        assert not result["applied"]
        empty.assert_not_called()
        assert not (root / "operations").exists()


def test_nonpublic_existing_content_refused(tmp_path):
    """Real PostgreSQL, separate unique disposable database; public is empty."""
    import os
    import uuid

    from sqlalchemy import create_engine, text
    from sqlalchemy.engine import make_url

    url = make_url(
        os.environ.get(
            "LABADDA_TEST_DATABASE_URL",
            "postgresql+psycopg://labadda:labadda-dev@localhost:5432/labadda_test",
        )
    )
    name = "labadda_commission_" + uuid.uuid4().hex
    admin = create_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    target = tmp_path / "candidate"
    target.mkdir()
    (target / "venv").symlink_to(Path(sys.prefix), target_is_directory=True)
    env = {
        "PATH": "/usr/bin:/bin",
        "LABADDA_DATABASE_URL": url.set(database=name).render_as_string(hide_password=False),
    }
    try:
        with admin.connect() as db:
            db.execute(text("CREATE DATABASE " + name))
        commission.empty_database(target, env)
        engine = create_engine(url.set(database=name))
        with engine.begin() as db:
            db.execute(text("CREATE SCHEMA pgx"))
            db.execute(text("CREATE TABLE pgx.preserved (id integer)"))
        engine.dispose()
        with pytest.raises(commission.operations.OperationsError):
            commission.empty_database(target, env)
    finally:
        with admin.connect() as db:
            db.execute(text("DROP DATABASE IF EXISTS " + name + " WITH (FORCE)"))
        admin.dispose()
