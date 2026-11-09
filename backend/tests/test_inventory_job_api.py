"""T28/T30: bounded operational metadata, refreshed capability, no content grant."""
from datetime import timedelta
import json
import uuid

import pytest
from sqlalchemy import delete

from labadda import inventory_jobs as jobs
from labadda.models import InventoryJob, UsageReaderGrant, User
from labadda.security import utcnow
from tests.test_panel import pair, PANEL


def delegate(db_factory, ids):
    with db_factory() as db:
        db.add(UsageReaderGrant(user_id=ids['users']['ben'], granted_by=ids['users']['admin'],
                               reason='Synthetic operational observer', expires_at=utcnow()+timedelta(hours=1)))
        db.commit()


def test_admin_and_observer_receive_sanitized_history(db_factory, ids, as_user, settings):
    settings.asset_dir.mkdir()
    job_id = jobs.enqueue(db_factory, 'private-request-label', {})
    result = jobs.run(db_factory, settings.asset_dir, job_id)
    delegate(db_factory, ids)
    for name in ['admin', 'ben']:
        api = as_user(name)
        response = api.get('/admin/inventory-jobs')
        assert response.status_code == 200
        listing = response.json()
        assert listing['jobs'][0]['id'] == str(job_id)
        assert listing['jobs'][0]['attempts'] == [] and not listing['history_included']
        detail = api.get(f'/admin/inventory-jobs/{job_id}').json()
        assert detail['attempts'][0]['receipt_id'] == result['id']
        assert not detail['enforcement_authority'] and not detail['deletion_authorized']
        assert 'private-request-label' not in json.dumps(detail)
        assert str(settings.asset_dir) not in json.dumps(detail)
        assert api.post(f'/admin/inventory-jobs/{job_id}', json={}).status_code == 405


def test_normal_nonobserver_and_anonymous_denied(db_factory, ids, as_user, make_client):
    job_id = jobs.enqueue(db_factory, 'permission-key', {})
    for path in ['/admin/inventory-jobs', f'/admin/inventory-jobs/{job_id}']:
        assert as_user('ben').get(path).status_code == 403
        assert make_client().get(path).status_code == 401


def test_panel_and_explicit_panel_markers_refused(db_factory, ids, as_user, make_client):
    job_id = jobs.enqueue(db_factory, 'panel-test-key', {})
    panel = pair(as_user, make_client, ids)
    for path in ['/admin/inventory-jobs', f'/admin/inventory-jobs/{job_id}']:
        assert panel.api.get(path, headers=PANEL).status_code == 401
        assert as_user('admin').get(path, headers=PANEL).status_code == 401
        assert as_user('admin').get(path + '?panel=1').status_code == 401


def test_stable_keyset_pagination_filter_and_limits(db_factory, ids, as_user):
    created = [jobs.enqueue(db_factory, f'page-key-{i}', {}) for i in range(5)]
    jobs.cancel(db_factory, created[0])
    api = as_user('admin')
    collected, cursor = [], None
    while True:
        page = api.get('/admin/inventory-jobs?limit=2' + (f'&before={cursor}' if cursor else '')).json()
        collected.extend(row['id'] for row in page['jobs'])
        cursor = page['next_cursor']
        if not cursor:
            break
    assert len(collected) == len(set(collected)) == 5
    assert set(collected) == {str(x) for x in created}
    filtered = api.get('/admin/inventory-jobs?state=cancelled').json()['jobs']
    assert [row['id'] for row in filtered] == [str(created[0])]
    for suffix in ['limit=0', 'limit=26', 'state=unknown', 'before=invalid']:
        assert api.get('/admin/inventory-jobs?' + suffix).status_code == 422
    assert api.get(f'/admin/inventory-jobs?before={uuid.uuid4()}').status_code == 404
    assert api.get(f'/admin/inventory-jobs/{uuid.uuid4()}').status_code == 404


def test_expired_lease_is_reported_without_mutating_job(db_factory, ids, as_user):
    job_id = jobs.enqueue(db_factory, 'stale-lease-key', {})
    jobs.claim(db_factory, job_id)
    with db_factory() as db:
        db.get(InventoryJob, job_id).lease_until = utcnow() - timedelta(seconds=1)
        db.commit()
    detail = as_user('admin').get(f'/admin/inventory-jobs/{job_id}').json()
    assert detail['state'] == 'running' and detail['lease_expired']
    assert detail['attempts'][0]['state'] == 'running'


@pytest.mark.parametrize('kind', ['list', 'detail'])
@pytest.mark.parametrize('loss', ['delegation', 'admin', 'session'])
def test_authority_loss_during_measurement_denies_response(db_factory, ids, as_user, monkeypatch, kind, loss):
    from labadda.api import inventory_jobs as api_jobs
    from labadda.models import AuthSession
    job_id = jobs.enqueue(db_factory, 'revocation-key', {})
    delegate(db_factory, ids)
    username = 'admin' if loss == 'admin' else 'ben'
    api = as_user(username)
    original = api_jobs.describe
    def revoke(*args, **kwargs):
        result = original(*args, **kwargs)
        with db_factory() as db:
            if loss == 'delegation':
                db.execute(delete(UsageReaderGrant))
            elif loss == 'admin':
                db.get(User, ids['users']['admin']).is_admin = False
            else:
                from sqlalchemy import update
                db.execute(update(AuthSession).where(AuthSession.user_id == ids['users']['ben']).values(revoked_at=utcnow()))
            db.commit()
        return result
    monkeypatch.setattr(api_jobs, 'describe', revoke)
    path = '/admin/inventory-jobs' + (f'/{job_id}' if kind == 'detail' else '')
    assert api.get(path).status_code == (401 if loss == 'session' else 403)
