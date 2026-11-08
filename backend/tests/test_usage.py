"""T17/T28/T30: partial meters never imply complete accounting or expose content."""
import json


def upload(api):
    return api.post('/uploads', files={'file': ('secret-name.pdf', b'%PDF-1.4\nfixture\n%%EOF', 'application/pdf')})


def test_users_only_measure_their_own_uploads(as_user):
    ben, chen = as_user('ben'), as_user('chen')
    response = upload(ben)
    assert response.status_code == 201
    size = response.json()['size']
    own = ben.get('/usage').json()
    assert own['measurement']['tracked_original_bytes'] == size
    assert own['measurement']['provisional_original_bytes'] == size
    assert chen.get('/usage').json()['measurement']['tracked_original_bytes'] == 0
    assert own['measurement']['complete_for_enforcement'] is False
    assert 'secret-name' not in json.dumps(own)
    assert not own['available_features']['archives']


def test_site_measurement_is_admin_only_and_unknown_is_not_zero(as_user, monkeypatch):
    from labadda.api import usage
    ben, admin = as_user('ben'), as_user('admin')
    assert upload(ben).status_code == 201
    assert ben.get('/admin/usage').status_code == 403
    monkeypatch.setattr(usage.os, 'statvfs', lambda _: (_ for _ in ()).throw(OSError('missing')))
    measured = admin.get('/admin/usage').json()
    assert measured['assets']['tracked_files'] == 1
    assert measured['filesystem']['state'] == 'unknown'
    assert measured['filesystem']['free_bytes'] is None
    assert 'secret-name' not in json.dumps(measured)
    assert 'password' not in json.dumps(measured)


def test_observation_history_is_explicit_and_audited(as_user):
    admin = as_user('admin')
    assert admin.get('/admin/usage-observations').json()['observations'] == []
    created = admin.post('/admin/usage-observations', json={})
    assert created.status_code == 201
    history = admin.get('/admin/usage-observations').json()
    assert history['observations'][0]['id'] == created.json()['id']
    assert any(e['action'] == 'usage.observe' for e in admin.get('/admin/audit').json()['events'])
    assert as_user('ben').post('/admin/usage-observations', json={}).status_code == 403


def test_saved_history_is_bounded(as_user, db_factory):
    from labadda.models import UsageObservation
    from sqlalchemy import select, func
    admin = as_user('admin')
    # Backfill old synthetic samples; exercise one real observation/prune commit.
    with db_factory() as db:
        from labadda.models import User
        owner = db.scalar(select(User).where(User.username == 'admin'))
        db.add_all([UsageObservation(schema_version=1, payload={}, created_by=owner.id) for _ in range(103)])
        db.commit()
    assert admin.post('/admin/usage-observations', json={}).status_code == 201
    with db_factory() as db:
        assert db.scalar(select(func.count()).select_from(UsageObservation)) == 100


def test_usage_cannot_select_another_user(as_user, ids):
    assert upload(as_user('ben')).status_code == 201
    result = as_user('chen').get('/usage', params={'user_id': ids['users']['ben']}).json()
    assert result['measurement']['tracked_files'] == 0
