"""Demo resets refuse production, remote and non-designated databases before connecting."""

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize(
    "environment,database",
    [
        ("pilot", "postgresql+psycopg://labadda:private@localhost/labadda_main"),
        ("test", "postgresql+psycopg://labadda:private@localhost/labadda_main"),
        ("test", "postgresql+psycopg://labadda:private@remote.invalid/labadda_simulation_review"),
    ],
)
def test_simulation_refuses_non_disposable_targets(monkeypatch, capsys, environment, database):
    spec = importlib.util.spec_from_file_location(
        "simulation_seed", ROOT / "scripts/seed_50_org_simulation.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "DATABASE_URL", database)
    monkeypatch.setenv("LABADDA_ENV", environment)
    monkeypatch.setattr(module, "session_factory", lambda *args: pytest.fail("must refuse before connecting"))
    with pytest.raises(SystemExit, match="Refusing reset"):
        module.seed_simulation()
    assert "private" not in capsys.readouterr().out
