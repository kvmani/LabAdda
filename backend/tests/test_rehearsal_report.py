"""T13: the S4 rehearsal gate fails on any integrity, delivery or isolation problem."""
import importlib.util
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[2] / 'scripts'
sys.path.insert(0, str(SCRIPTS))  # rehearsal.py imports shared helpers from soak.py
spec = importlib.util.spec_from_file_location('rehearsal', SCRIPTS / 'rehearsal.py')
rehearsal = importlib.util.module_from_spec(spec)
sys.modules['rehearsal'] = rehearsal  # dataclasses resolve their module through sys.modules
spec.loader.exec_module(rehearsal)


def valid():
    return {'workload': {'clients': 5, 'clients_subscribed': 5, 'workspaces': 2}, 'board_ops_acknowledged': 10, 'chat_messages_acknowledged': 3, 'deliveries_expected': 100,
            'deliveries_missing': 0, 'isolation_violations': 0, 'lost': 0, 'duplicates': 0,
            'revision_gaps': False, 'error_count': 0, 'targets': {'update': True, 'list': True}}


def test_healthy_rehearsal_passes():
    assert rehearsal.report_passes(valid(), enforce_targets=True)


@pytest.mark.parametrize(('field', 'value'), [
    ('board_ops_acknowledged', 0), ('chat_messages_acknowledged', 0), ('deliveries_expected', 0),
    ('deliveries_missing', 1), ('isolation_violations', 1), ('lost', 1), ('duplicates', 1),
    ('revision_gaps', True), ('error_count', 1)])
def test_integrity_delivery_and_isolation_failures_cannot_pass(field, value):
    report = valid()
    report[field] = value
    assert not rehearsal.report_passes(report, enforce_targets=False)


def test_latency_targets_fail_only_when_enforced():
    report = valid()
    report['targets']['update'] = False
    assert rehearsal.report_passes(report, enforce_targets=False)
    assert not rehearsal.report_passes(report, enforce_targets=True)


def test_partially_subscribed_workload_cannot_pass():
    report = valid()
    report['workload']['clients_subscribed'] = 4
    assert not rehearsal.report_passes(report, enforce_targets=False)
