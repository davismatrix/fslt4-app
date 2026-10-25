import importlib
import sys

import pytest
from fastapi.testclient import TestClient

@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv('CHURCH_DATA_DIR', str(tmp_path))
    sys.modules.pop('app', None)
    module = importlib.import_module('app')
    with module.db() as con:
        for name, role in [('Admin','admin'),('Alice','member'),('Bob','member')]:
            con.execute('INSERT INTO users(name,email,password,role) VALUES (?,?,?,?)', (name,name.lower()+'@church.org',module.password_hash('correct-horse-battery'),role))
    return TestClient(module.app)

def auth(client, name):
    res = client.post('/api/login', json={'email':name+'@church.org','password':'correct-horse-battery'})
    assert res.status_code == 200
    return {'Authorization':'Bearer '+res.json()['token']}

def test_member_privacy_and_logout(client):
    admin = auth(client,'admin')
    alice = auth(client,'alice')
    bob = auth(client,'bob')
    res = client.post('/api/members/2/slips/2025',content=b'%PDF-1.4\nexample',headers=admin)
    assert res.status_code == 201
    slip = res.json()['id']
    assert client.get('/api/slips',headers=bob).json() == []
    assert client.get(f'/api/slips/{slip}/download',headers=bob).status_code == 404
    assert client.get(f'/api/slips/{slip}/download').status_code == 401
    result = client.get(f'/api/slips/{slip}/download',headers=alice)
    assert result.content.startswith(b'%PDF-')
    assert result.headers['cache-control'] == 'no-store'
    assert client.get('/api/members',headers=alice).status_code == 403
    assert client.post('/api/logout',headers=alice).status_code == 200
    assert client.get('/api/me',headers=alice).status_code == 401

def test_upload_validation_and_duplicate(client):
    admin = auth(client,'admin')
    alice = auth(client,'alice')
    path = '/api/members/2/slips/2025'
    assert client.post(path,content=b'%PDF-1.4',headers=alice).status_code == 403
    assert client.post(path,content=b'not pdf',headers=admin).status_code == 400
    assert client.post(path,content=b'%PDF-1.4',headers=admin).status_code == 201
    assert client.post(path,content=b'%PDF-1.4',headers=admin).status_code == 409
    assert client.post('/api/members/999/slips/2025',content=b'%PDF-1.4',headers=admin).status_code == 404
    assert client.post('/api/login',json={'email':'alice@church.org','password':'wrong'}).status_code == 401


def batch_zip(csv_text='filename,email,year\nalice.pdf,alice@church.org,2025\nbob.pdf,bob@church.org,2025\n', files=None):
    import io
    import zipfile
    output = io.BytesIO()
    with zipfile.ZipFile(output, 'w') as archive:
        archive.writestr('members.csv', csv_text)
        for name, data in (files if files is not None else {'alice.pdf': b'%PDF-1.4 Alice', 'bob.pdf': b'%PDF-1.4 Bob'}).items():
            archive.writestr(name, data)
    return output.getvalue()


def test_batch_admin_only_and_success(client):
    admin = auth(client, 'admin')
    member = auth(client, 'alice')
    data = batch_zip()
    for path in ['/api/batches/preview', '/api/batches/confirm?digest=x']:
        assert client.post(path, content=data).status_code == 401
        assert client.post(path, content=data, headers=member).status_code == 403
    preview = client.post('/api/batches/preview', content=data, headers=admin).json()
    assert preview['valid'] and len(preview['rows']) == 2
    assert client.get('/api/slips', headers=admin).json() == []
    result = client.post('/api/batches/confirm?digest='+preview['digest'], content=data, headers=admin)
    assert result.status_code == 201 and result.json()['uploaded'] == 2
    slips = client.get('/api/slips', headers=member).json()
    assert len(slips) == 1
    assert client.get(f"/api/slips/{slips[0]['id']}/download", headers=member).content == b'%PDF-1.4 Alice'
    assert client.post('/api/batches/confirm?digest='+preview['digest'], content=data, headers=admin).status_code == 409


def test_batch_invalid_is_atomic_and_rechecks_conflicts(client):
    admin = auth(client, 'admin')
    data = batch_zip()
    preview = client.post('/api/batches/preview', content=data, headers=admin).json()
    assert client.post('/api/batches/confirm?digest=changed', content=data, headers=admin).status_code == 409
    client.post('/api/members/3/slips/2025', content=b'%PDF-1.4 existing', headers=admin)
    assert client.post('/api/batches/confirm?digest='+preview['digest'], content=data, headers=admin).status_code == 409
    assert len(client.get('/api/slips', headers=admin).json()) == 1


@pytest.mark.parametrize('data', [
    b'not a zip',
    batch_zip(files={'../alice.pdf': b'%PDF-1.4'}),
    batch_zip('wrong,headers\na,b\n'),
])
def test_malformed_batch(client, data):
    assert client.post('/api/batches/preview', content=data, headers=auth(client, 'admin')).status_code == 400


def test_batch_row_errors(client):
    admin = auth(client, 'admin')
    data = batch_zip('filename,email,year\nalice.pdf,missing@church.org,2025\nalice.pdf,alice@church.org,2025\nmissing.pdf,alice@church.org,2025\nbob.pdf,bob@church.org,1800\n', {'alice.pdf': b'bad', 'bob.pdf': b'%PDF-1.4'})
    preview = client.post('/api/batches/preview', content=data, headers=admin).json()
    assert not preview['valid']
    assert all(row['errors'] for row in preview['rows'])
    assert client.post('/api/batches/confirm?digest='+preview['digest'], content=data, headers=admin).status_code == 409
    assert client.get('/api/slips', headers=admin).json() == []


@pytest.mark.parametrize('status', ['sent', 'not_configured', 'failed'])
def test_create_member_notification(client, monkeypatch, status):
    from unittest.mock import MagicMock
    module = sys.modules['app']
    sender = MagicMock(return_value=status)
    monkeypatch.setattr(module, 'send_welcome', sender)
    admin = auth(client, 'admin')
    data = {'name':'Jane Doe', 'email':'JANE@church.org','password':'private-password-123'}
    response = client.post('/api/members', json=data, headers=admin)
    assert response.status_code == 201
    assert response.json()['notification'] == status
    sender.assert_called_once_with('Jane Doe', 'jane@church.org')
    assert client.post('/api/login', json={'email':'jane@church.org','password':data['password']}).status_code == 200
    assert client.post('/api/members', json=data, headers=admin).status_code == 409
    sender.assert_called_once()


def test_member_creation_email_validation_and_authorization(client, monkeypatch):
    from unittest.mock import MagicMock
    sender = MagicMock()
    monkeypatch.setattr(sys.modules['app'], 'send_welcome', sender)
    data = {'name':'Jane','email':'jane@church.org','password':'private-password-123'}
    assert client.post('/api/members', json=data, headers=auth(client, 'alice')).status_code == 403
    data['email'] = 'jane@church.org\nBcc: someone@example.com'
    assert client.post('/api/members', json=data, headers=auth(client, 'admin')).status_code == 422
    sender.assert_not_called()


@pytest.mark.parametrize('prefix', ['', 'donation-slips-2025/'])
def test_batch_macos_zip(client, prefix):
    import io
    import zipfile
    output = io.BytesIO()
    with zipfile.ZipFile(output, 'w') as archive:
        if prefix:
            archive.writestr(prefix, b'')
        archive.writestr(prefix+'members.csv', 'filename,email,year\nalice.pdf,alice@church.org,2025\n')
        archive.writestr(prefix+'alice.pdf', b'%PDF-1.4 Alice')
        archive.writestr(prefix+'.DS_Store', b'metadata')
        archive.writestr('__MACOSX/'+prefix+'._alice.pdf', b'metadata')
    data = output.getvalue()
    admin = auth(client, 'admin')
    response = client.post('/api/batches/preview', content=data, headers=admin)
    assert response.status_code == 200
    preview = response.json()
    assert preview['valid']
    assert client.post('/api/batches/confirm?digest='+preview['digest'], content=data, headers=admin).json() == {'uploaded': 1}


@pytest.mark.parametrize('filename', ['/alice.pdf', 'folder/../alice.pdf', 'folder\\alice.pdf', 'other/alice.pdf'])
def test_batch_rejects_unsafe_or_mixed_paths(client, filename):
    data = batch_zip(files={filename: b'%PDF-1.4'})
    assert client.post('/api/batches/preview', content=data, headers=auth(client, 'admin')).status_code == 400


@pytest.mark.parametrize('encoding', ['utf-8-sig', 'utf-16', 'cp1252'])
def test_batch_csv_encodings(client, encoding):
    import io
    import zipfile
    output = io.BytesIO()
    filename = 'André.pdf'
    with zipfile.ZipFile(output, 'w') as archive:
        archive.writestr('members.csv', f'filename,email,year\n{filename},alice@church.org,2025\n'.encode(encoding))
        archive.writestr(filename, b'%PDF-1.4 Alice')
    data = output.getvalue()
    admin = auth(client, 'admin')
    response = client.post('/api/batches/preview', content=data, headers=admin)
    assert response.status_code == 200
    preview = response.json()
    assert preview['valid']
    assert preview['rows'][0]['filename'] == filename
    assert client.post('/api/batches/confirm?digest='+preview['digest'], content=data, headers=admin).status_code == 201


@pytest.mark.parametrize('raw', [b'PK\x03\x04workbook', b'\xd0\xcf\x11\xe0workbook', b'filename,email,year\x00', b'\xff\xfe\x01', b'\x81invalid'])
def test_binary_or_invalid_csv_has_actionable_error(client, raw):
    import io
    import zipfile
    output = io.BytesIO()
    with zipfile.ZipFile(output, 'w') as archive:
        archive.writestr('members.csv', raw)
    result = client.post('/api/batches/preview', content=output.getvalue(), headers=auth(client, 'admin'))
    assert result.status_code == 400
    assert 'CSV UTF-8 in Excel' in result.json()['detail']
    assert 'codec' not in result.json()['detail']


def test_slip_preview_privacy_headers_and_audit(client):
    admin = auth(client, 'admin')
    alice = auth(client, 'alice')
    bob = auth(client, 'bob')
    pdf = b'%PDF-1.4 preview document'
    slip_id = client.post('/api/members/2/slips/2025', content=pdf, headers=admin).json()['id']
    path = f'/api/slips/{slip_id}/preview'
    assert client.get(path).status_code == 401
    assert client.get(path, headers=bob).status_code == 404
    assert client.get('/api/slips/99999/preview', headers=alice).status_code == 404
    for headers in (alice, admin):
        response = client.get(path, headers=headers)
        assert response.status_code == 200
        assert response.content == pdf
        assert response.headers['content-type'] == 'application/pdf'
        assert response.headers['content-disposition'].startswith('inline;')
        assert response.headers['cache-control'] == 'no-store'
        assert response.headers['x-content-type-options'] == 'nosniff'
    assert client.get(f'/api/slips/{slip_id}/download', headers=alice).headers['content-disposition'].startswith('attachment;')
    with sys.modules['app'].db() as con:
        assert con.execute("SELECT count(*) FROM audit WHERE action='preview' AND slip_id=?", (slip_id,)).fetchone()[0] == 2
    client.post('/api/logout', headers=alice)
    assert client.get(path, headers=alice).status_code == 401


def test_member_access_revoke_restore(client):
    admin = auth(client, 'admin')
    alice = auth(client, 'alice')
    slip_id = client.post('/api/members/2/slips/2025', content=b'%PDF-1.4 Alice', headers=admin).json()['id']
    assert client.post('/api/members/2/access', json={'active': False}, headers=admin).status_code == 200
    assert client.get('/api/me', headers=alice).status_code == 401
    assert client.get(f'/api/slips/{slip_id}/preview', headers=alice).status_code == 401
    assert client.get(f'/api/slips/{slip_id}/download', headers=alice).status_code == 401
    assert client.post('/api/login', json={'email':'alice@church.org','password':'correct-horse-battery'}).status_code == 401
    members = client.get('/api/members', headers=admin).json()
    member = next(m for m in members if m['id'] == 2)
    assert member['active'] == 0 and member['slip_count'] == 1
    assert 'password' not in member
    assert client.get(f'/api/slips/{slip_id}/preview', headers=admin).status_code == 200
    assert client.post('/api/members/2/access', json={'active': True}, headers=admin).status_code == 200
    assert client.get('/api/me', headers=alice).status_code == 401
    assert client.get('/api/me', headers=auth(client, 'alice')).status_code == 200


def test_member_deletion_removes_access_and_slips(client):
    admin = auth(client, 'admin')
    alice = auth(client, 'alice')
    slip_id = client.post('/api/members/2/slips/2025', content=b'%PDF-1.4 Alice', headers=admin).json()['id']
    assert client.delete('/api/members/2', headers=admin).status_code == 200
    assert client.get('/api/me', headers=alice).status_code == 401
    assert client.get(f'/api/slips/{slip_id}/download', headers=admin).status_code == 404
    assert all(m['id'] != 2 for m in client.get('/api/members', headers=admin).json())
    with sys.modules['app'].db() as con:
        assert con.execute('SELECT count(*) FROM sessions WHERE user_id=2').fetchone()[0] == 0
        assert con.execute('SELECT count(*) FROM slips WHERE member_id=2').fetchone()[0] == 0
        assert con.execute("SELECT count(*) FROM management_audit WHERE member_id=2 AND action='delete_member'").fetchone()[0] == 1


def test_admin_slip_replacement_and_deletion(client):
    admin = auth(client, 'admin')
    alice = auth(client, 'alice')
    slip_id = client.post('/api/members/2/slips/2025', content=b'%PDF-1.4 original', headers=admin).json()['id']
    path = f'/api/slips/{slip_id}'
    assert client.post(path+'/replace', content=b'not PDF', headers=admin).status_code == 400
    assert client.get(path+'/download', headers=alice).content == b'%PDF-1.4 original'
    assert client.post(path+'/replace', content=b'%PDF-1.4 corrected', headers=admin).status_code == 200
    assert client.get(path+'/download', headers=alice).content == b'%PDF-1.4 corrected'
    assert client.get('/api/slips', headers=alice).json()[0]['member_id'] == 2
    assert client.delete(path, headers=admin).status_code == 200
    assert client.get('/api/slips', headers=alice).json() == []
    assert client.get(path+'/preview', headers=alice).status_code == 404


@pytest.mark.parametrize('method,path,kwargs', [
    ('post','/api/members/2/access', {'json':{'active':False}}),
    ('delete','/api/members/2', {}),
    ('delete','/api/slips/1', {}),
    ('post','/api/slips/1/replace', {'content':b'%PDF-1.4'}),
])
def test_member_management_admin_only(client, method, path, kwargs):
    assert client.request(method, path, **kwargs).status_code == 401
    assert client.request(method, path, headers=auth(client, 'alice'), **kwargs).status_code == 403


def test_management_missing_targets_and_admin_protection(client):
    admin = auth(client, 'admin')
    for member_id in (1, 999):
        assert client.delete(f'/api/members/{member_id}', headers=admin).status_code == 404
        assert client.post(f'/api/members/{member_id}/access', json={'active':False}, headers=admin).status_code == 404
    assert client.delete('/api/slips/999', headers=admin).status_code == 404
    assert client.post('/api/slips/999/replace', content=b'%PDF-1.4', headers=admin).status_code == 404
    assert client.get('/api/me', headers=admin).status_code == 200


def test_existing_database_gets_active_column(tmp_path, monkeypatch):
    import sqlite3
    with sqlite3.connect(tmp_path / 'church.db') as con:
        con.execute('CREATE TABLE users(id INTEGER PRIMARY KEY, name TEXT NOT NULL, email TEXT UNIQUE NOT NULL, password TEXT NOT NULL, role TEXT NOT NULL)')
        con.execute("INSERT INTO users VALUES (1,'Existing','existing@church.org','hash','member')")
    monkeypatch.setenv('CHURCH_DATA_DIR', str(tmp_path))
    sys.modules.pop('app', None)
    module = importlib.import_module('app')
    with module.db() as con:
        assert con.execute('SELECT active FROM users WHERE id=1').fetchone()[0] == 1
