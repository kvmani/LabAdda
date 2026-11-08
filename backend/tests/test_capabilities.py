"""T28 foundation: explicit metadata grants must not turn a member into admin."""
from datetime import timedelta

from labadda.fixtures import fixture_password
from labadda.models import UsageReaderGrant
from labadda.security import utcnow


def grant(admin, target_id, **overrides):
    return admin.post('/admin/usage-readers',json={'user_id':target_id,'hours':24,
        'reason':'Synthetic operator walkthrough','password':fixture_password(),**overrides})


def test_reader_can_read_metadata_but_not_administer_or_read_private_content(as_user, ids):
    admin, ben = as_user('admin'), as_user('ben')
    assert not ben.get('/capabilities').json()['usage.read']
    assert grant(admin, ids['users']['ben']).status_code == 201
    assert ben.get('/capabilities').json()['usage.read']
    assert ben.get('/admin/usage').status_code == 200
    assert ben.get('/admin/storage-inspections').status_code == 200
    assert ben.get('/admin/usage-observations').status_code == 200
    assert ben.get('/admin/policy-drafts').status_code == 403
    assert ben.get('/admin/users').status_code == 403
    assert ben.post('/admin/usage-observations',json={}).status_code == 403
    private = as_user('asha').post('/notes',json={'title':'Private fixture','body':'Not for observers'}).json()
    assert ben.get(f"/notes/{private['id']}").status_code == 404
    assert ben.get('/admin/usage-readers').status_code == 403
    assert grant(ben, ids['users']['chen']).status_code == 403


def test_password_confirmation_no_grant_or_secret_audit(as_user, ids):
    admin = as_user('admin')
    assert grant(admin, ids['users']['ben'],password='incorrect-test-secret').status_code == 403
    assert not as_user('ben').get('/capabilities').json()['usage.read']
    audit = admin.get('/admin/audit').json()
    assert 'incorrect-test-secret' not in str(audit)
    assert any(e['action']=='usage.reader.reauthenticate' and e['outcome']=='denied' for e in audit['events'])


def test_revoke_and_expiry_remove_access(as_user, ids, db_factory):
    admin, ben = as_user('admin'), as_user('ben')
    assert grant(admin, ids['users']['ben']).status_code == 201
    with db_factory() as db:
        row = db.get(UsageReaderGrant, ids['users']['ben'])
        row.expires_at = utcnow()-timedelta(seconds=1); db.commit()
    assert ben.get('/admin/usage').status_code == 403
    assert grant(admin, ids['users']['ben']).status_code == 201
    result=admin.post('/admin/usage-readers/revoke',json={'user_id':ids['users']['ben'],
        'reason':'Walkthrough complete','password':fixture_password()})
    assert result.status_code == 200
    assert ben.get('/admin/usage').status_code == 403
    assert any(e['action']=='usage.reader.revoke' for e in admin.get('/admin/audit').json()['events'])


def test_invalid_grants_never_change_role(as_user, ids):
    admin=as_user('admin')
    for fields in ({'hours':0},{'hours':True},{'hours':721},{'reason':'   '},{'user_id':ids['users']['admin']},{'user_id':ids['users']['fay']}):
        assert grant(admin,ids['users']['ben'],**fields).status_code == 422
    assert not as_user('ben').get('/capabilities').json()['identity.admin']


def test_grant_and_identity_update_do_not_deadlock(make_client, ids, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    import threading
    from labadda import audit
    from labadda.api import capabilities
    grant_client, patch_client = make_client('admin'), make_client('admin')
    actor_locked, target_locked = threading.Event(), threading.Event()
    authenticate = capabilities.authenticate_action
    record = audit.record
    def intercepted_auth(*args):
        authenticate(*args)
        actor_locked.set()
        assert target_locked.wait(5)
    def intercepted_audit(db, **kwargs):
        if kwargs['action'] == 'identity.update':
            target_locked.set()
        return record(db, **kwargs)
    monkeypatch.setattr(capabilities, 'authenticate_action', intercepted_auth)
    monkeypatch.setattr(audit, 'record', intercepted_audit)
    with ThreadPoolExecutor(max_workers=2) as pool:
        granting = pool.submit(grant, grant_client, ids['users']['ben'])
        assert actor_locked.wait(5)
        updating = pool.submit(patch_client.patch, f"/admin/users/{ids['users']['ben']}", json={'display_name':'Ben Fixture Updated'})
        assert granting.result(timeout=10).status_code == 201
        assert updating.result(timeout=10).status_code == 200


def test_reader_listing_is_active_first_and_reports_truncation(as_user, ids, db_factory):
    from labadda.models import User
    admin = as_user('admin')
    with db_factory() as db:
        for i in range(201):
            user = User(username=f'expired_reader_{i}',display_name='Expired synthetic observer')
            db.add(user); db.flush()
            db.add(UsageReaderGrant(user_id=user.id, granted_by=ids['users']['admin'],
                reason='Expired fixture', expires_at=utcnow()-timedelta(days=1)))
        db.commit()
    assert grant(admin, ids['users']['ben']).status_code == 201
    listed = admin.get('/admin/usage-readers').json()
    assert listed['truncated'] and listed['total_count'] == 202
    assert listed['grants'][0]['user_id'] == ids['users']['ben']


def test_password_confirmation_also_requires_csrf(as_user, ids):
    admin = as_user('admin')
    response = admin.client.post(admin.url('/admin/usage-readers'),json={
        'user_id':ids['users']['ben'],'hours':24,'reason':'Synthetic request','password':fixture_password()})
    assert response.status_code == 403
    assert not as_user('ben').get('/capabilities').json()['usage.read']
