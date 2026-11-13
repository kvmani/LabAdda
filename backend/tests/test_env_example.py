"""The example environment file must list every setting the server reads."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
NOT_FOR_OPERATORS = {"LABADDA_TEST_HEALTH_FORCE"}  # test-only switch, ignored outside development


def test_example_lists_every_setting_in_config():
    read = set(re.findall(r'"(LABADDA_[A-Z0-9_]+)"', (ROOT / "backend/labadda/config.py").read_text()))
    listed = set(re.findall(r"^LABADDA_[A-Z0-9_]+", (ROOT / "deploy/labadda.env.example").read_text(), re.M))
    assert read - NOT_FOR_OPERATORS <= listed
