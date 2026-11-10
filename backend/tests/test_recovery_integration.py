"""T12 real PostgreSQL recovery; enabled explicitly with LABADDA_RECOVERY_TESTS=1."""
import os
import shutil
import uuid
from dataclasses import replace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from labadda.app import create_app
from labadda.recovery import RecoveryError, backup, restore
from tests.conftest import Api
from tests.test_chat_board import stroke
from tests.test_panel import pair, PANEL

pytestmark = pytest.mark.skipif(os.environ.get('LABADDA_RECOVERY_TESTS') != '1',
                                reason='enable explicit disposable database recovery rehearsal')


def test_full_recovery_preserves_content_and_revokes_credentials(settings, ids, as_user, make_client, tmp_path):
    assert shutil.which('pg_dump') and shutil.which('pg_restore'), 'PostgreSQL 16 clients required'
    workspace = ids['workspaces']['section_a']
    ben = as_user('ben')
    pdf = b'%PDF-1.4\nSynthetic recovery document\n%%EOF'
    upload = ben.post('/uploads', headers={'Idempotency-Key': 'recovery-request-01'},
                      files={'file': ('fixture.pdf', pdf, 'application/pdf')})
    assert upload.status_code == 201
    asset = upload.json()
    from io import BytesIO
    from PIL import Image
    image = BytesIO()
    Image.new('RGB', (12, 9), 'blue').save(image, format='PNG')
    picture = ben.post('/uploads', files={'file': ('recovery.png', image.getvalue(), 'image/png')})
    assert picture.status_code == 201
    picture_id = picture.json()['id']
    preview = ben.get(f'/files/{picture_id}/preview').content
    post = ben.post(f'/workspaces/{workspace}/posts', json={'body': 'Recovery post', 'attachment_ids': [asset['id'], picture_id]})
    assert post.status_code == 201
    note = ben.post('/notes', json={'title': 'Private recovery note', 'body': 'fixture'})
    assert note.status_code == 201
    assert ben.post(f'/workspaces/{workspace}/chat', json={'body': 'Recovery chat', 'client_id': 'recover-chat-01'}).status_code == 201
    assert ben.post(f'/workspaces/{workspace}/board/ops', json=stroke('recover-stroke-01', 'recovered-line')).status_code == 200
    panel = pair(as_user, make_client, ids)
    unused_code = ben.post('/panel/pairings', json={'workspace_id': workspace}).json()['code']
    pending = as_user('admin').post('/admin/users', json={'username': 'restore_pending', 'display_name': 'Pending Fixture'})
    assert pending.status_code == 201
    activation_token = pending.json()['activation_token']
    old_cookies = dict(ben.client.cookies)
    old_panel_cookies = dict(panel.api.client.cookies)
    from labadda.fixtures import fixture_password
    granted = as_user('admin').post('/admin/usage-readers', json={'user_id':ids['users']['ben'],
        'hours':24,'reason':'Synthetic recovery observer','password':fixture_password()})
    assert granted.status_code == 201
    assert ben.get('/admin/usage').status_code == 200
    from labadda.models import UploadReservation
    from labadda.db import session_factory
    from labadda.security import utcnow
    from datetime import timedelta
    with session_factory(settings.database_url)() as db:
        db.add(UploadReservation(user_id=ids['users']['ben'],bytes=123,
            created_at=utcnow(),expires_at=utcnow()+timedelta(minutes=10)))
        db.commit()
    from labadda import inventory_jobs
    job_id = inventory_jobs.enqueue(session_factory(settings.database_url), 'recovery-inventory', {})
    inventory_jobs.claim(session_factory(settings.database_url), job_id)
    todo = ben.post('/todos/lists', json={'client_id':str(uuid.uuid4()), 'title':'Recovery tasks'}).json()
    todo_task = ben.post(f"/todos/lists/{todo['id']}/tasks", json={
        'client_id':str(uuid.uuid4()), 'title':'Recovered task', 'checklist':[{'title':'Check replay','done':True}]}).json()
    bundle = tmp_path / 'backup'
    sha = backup(settings.database_url, settings.asset_dir, bundle, 'synthetic-release', writers_quiesced=True)
    target_name = 'labadda_restore_test_' + uuid.uuid4().hex
    admin = create_engine(settings.database_url, isolation_level='AUTOCOMMIT')
    target_url = str(admin.url.set(database=target_name).render_as_string(hide_password=False))
    created = False
    try:
        with admin.connect() as conn:
            conn.execute(text(f'CREATE DATABASE "{target_name}"'))
            created = True
        target_assets = tmp_path / 'restored-assets'
        result = restore(bundle, sha, target_url, target_assets, isolated_target=True)
        assert result['sessions_revoked']
        from labadda.models import InventoryJob, InventoryAttempt
        with session_factory(target_url)() as db:
            assert db.get(InventoryJob, job_id).state == 'paused'
            assert db.get(InventoryJob, job_id).lease_until is None
            assert db.get(InventoryAttempt, (job_id, 1)).state == 'paused'
        restored = replace(settings, database_url=target_url, asset_dir=target_assets)
        with TestClient(create_app(restored)) as client:
            client.cookies.update(old_cookies)
            assert client.get('/api/v1/auth/session').status_code == 401
            client.cookies.clear()
            client.cookies.update(old_panel_cookies)
            assert client.get(f'/api/v1/workspaces/{workspace}/board', headers=PANEL).status_code == 401
            client.cookies.clear()
            assert client.post('/api/v1/panel/claim', json={'code': unused_code}).status_code == 422
            assert client.post('/api/v1/auth/activate', json={'token': activation_token, 'password': 'fixture-pass-123'}).status_code == 422
            api = Api(client, '/api/v1')
            assert api.login('ben').status_code == 200
            recovered_tasks = api.get(f"/todos/lists/{todo['id']}/tasks").json()['items']
            assert recovered_tasks[0]['id'] == todo_task['id']
            assert recovered_tasks[0]['checklist'][0]['done'] is True
            recovered_history=api.get(f"/todos/lists/{todo['id']}/tasks/{todo_task['id']}/history").json()['items']
            assert recovered_history[0]['action']=='created'
            assert api.get('/admin/usage').status_code == 403
            assert api.get('/usage').json()['measurement']['pending_upload_original_bytes'] == 0
            assert api.get('/uploads/requests/recovery-request-01').status_code == 404
            assert any(p["id"] == post.json()["id"] and p["body"] == "Recovery post" for p in api.get(f"/workspaces/{workspace}/posts").json()["posts"])
            assert api.get(f"/notes/{note.json()['id']}").json()['title'] == 'Private recovery note'
            assert api.get(f"/files/{asset['id']}").content == pdf
            assert api.get(f'/files/{picture_id}/preview').content == preview
            assert api.get(f'/workspaces/{workspace}/chat').json()['messages'][0]['body'] == 'Recovery chat'
            board = api.get(f'/workspaces/{workspace}/board').json()
            assert any(op['object_id'] == 'recovered-line' for op in board['ops'])
            assert api.login('chen').status_code == 200
            assert api.get(f"/files/{asset['id']}").status_code == 404
            assert api.get(f'/workspaces/{workspace}/board').status_code == 404
            assert api.login('admin').status_code == 200
            assert api.get(f"/notes/{note.json()['id']}").status_code == 404
        with pytest.raises(RecoveryError, match='must be empty'):
            restore(bundle, sha, target_url, tmp_path / 'second-assets', isolated_target=True)
        assert not (tmp_path / 'second-assets').exists()
    finally:
        if created:
            with admin.connect() as conn:
                conn.execute(text(f'DROP DATABASE "{target_name}" WITH (FORCE)'))
        admin.dispose()
