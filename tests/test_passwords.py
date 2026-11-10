import sys
from unittest.mock import MagicMock

import pytest

from test_api import auth, client  # noqa: F401  (fixture reuse)

NEW = 'a-brand-new-passphrase'


def login(client, email, password):
    return client.post('/api/login', json={'email': email, 'password': password})


def test_new_member_must_change_temporary_password(client, monkeypatch):
    monkeypatch.setattr(sys.modules['app'], 'send_welcome', MagicMock(return_value='sent'))
    admin = auth(client, 'admin')
    assert client.post('/api/members', json={'name': 'Jane', 'email': 'jane@church.org', 'password': 'temporary-pass-42'}, headers=admin).status_code == 201
    result = login(client, 'jane@church.org', 'temporary-pass-42')
    assert result.json()['user']['must_change_password'] is True
    jane = {'Authorization': 'Bearer ' + result.json()['token']}
    # Only /me, /logout, and /password work until the password is replaced.
    assert client.get('/api/slips', headers=jane).status_code == 403
    assert client.get('/api/me', headers=jane).status_code == 200
    changed = client.post('/api/password', json={'current_password': 'temporary-pass-42', 'new_password': NEW}, headers=jane)
    assert changed.status_code == 200 and changed.json()['must_change_password'] is False
    assert client.get('/api/slips', headers=jane).status_code == 200
    assert login(client, 'jane@church.org', NEW).status_code == 200


def test_change_password_checks_current_and_signs_out_other_sessions(client):
    first = auth(client, 'alice')
    second = auth(client, 'alice')
    assert client.post('/api/password', json={'current_password': 'wrong', 'new_password': NEW}, headers=first).status_code == 400
    assert client.post('/api/password', json={'current_password': 'correct-horse-battery', 'new_password': 'correct-horse-battery'}, headers=first).status_code == 422
    assert client.post('/api/password', json={'current_password': 'correct-horse-battery', 'new_password': NEW}, headers=first).status_code == 200
    assert client.get('/api/me', headers=first).status_code == 200
    assert client.get('/api/me', headers=second).status_code == 401
    assert login(client, 'alice@church.org', 'correct-horse-battery').status_code == 401
    assert client.post('/api/password', json={'current_password': NEW, 'new_password': 'x' * 12}).status_code == 401


def test_change_password_is_throttled(client, monkeypatch):
    monkeypatch.setattr(sys.modules['app'], 'LOGIN_ACCOUNT_LIMIT', 2)
    alice = auth(client, 'alice')
    for _ in range(2):
        assert client.post('/api/password', json={'current_password': 'wrong', 'new_password': NEW}, headers=alice).status_code == 400
    assert client.post('/api/password', json={'current_password': 'correct-horse-battery', 'new_password': NEW}, headers=alice).status_code == 429


@pytest.mark.parametrize('password', ['short', 'aaaaaaaaaaaaaaaa', 'Password1234', 'alice-is-my-name', 'x' * 129])
def test_password_policy(client, password):
    alice = auth(client, 'alice')
    result = client.post('/api/password', json={'current_password': 'correct-horse-battery', 'new_password': password}, headers=alice)
    assert result.status_code == 422


def test_create_member_rejects_weak_password(client, monkeypatch):
    sender = MagicMock()
    monkeypatch.setattr(sys.modules['app'], 'send_welcome', sender)
    data = {'name': 'Jane', 'email': 'jane@church.org', 'password': 'jane@church.org!'}
    assert client.post('/api/members', json=data, headers=auth(client, 'admin')).status_code == 422
    sender.assert_not_called()


def test_forgot_password_flow(client, monkeypatch):
    sender = MagicMock(return_value='sent')
    monkeypatch.setattr(sys.modules['app'], 'send_password_reset', sender)
    session = auth(client, 'alice')
    # Unknown accounts get the same response and no email.
    assert client.post('/api/password-reset', json={'email': 'nobody@church.org'}).json() == {'ok': True}
    sender.assert_not_called()
    assert client.post('/api/password-reset', json={'email': 'ALICE@church.org'}).json() == {'ok': True}
    first_token = sender.call_args.args[2]
    client.post('/api/password-reset', json={'email': 'alice@church.org'})
    token = sender.call_args.args[2]
    reset = '/api/password-reset/confirm'
    assert client.post(reset, json={'token': first_token, 'password': NEW}).status_code == 400
    assert client.post(reset, json={'token': token, 'password': 'aaaaaaaaaaaaaaaa'}).status_code == 422
    assert client.post(reset, json={'token': token, 'password': NEW}).status_code == 200
    assert client.post(reset, json={'token': token, 'password': NEW + '2'}).status_code == 400
    assert client.get('/api/me', headers=session).status_code == 401
    assert login(client, 'alice@church.org', NEW).status_code == 200


def test_reset_link_expires_and_ignores_revoked_accounts(client, monkeypatch):
    module = sys.modules['app']
    sender = MagicMock(return_value='sent')
    monkeypatch.setattr(module, 'send_password_reset', sender)
    client.post('/api/password-reset', json={'email': 'alice@church.org'})
    with module.db() as con:
        con.execute('UPDATE password_resets SET expires=0')
    assert client.post('/api/password-reset/confirm', json={'token': sender.call_args.args[2], 'password': NEW}).status_code == 400
    with module.db() as con:
        con.execute('UPDATE users SET active=0 WHERE id=2')
    sender.reset_mock()
    client.post('/api/password-reset', json={'email': 'alice@church.org'})
    sender.assert_not_called()


def test_password_reset_requests_are_throttled(client, monkeypatch):
    monkeypatch.setattr(sys.modules['app'], 'send_password_reset', MagicMock())
    monkeypatch.setattr(sys.modules['app'], 'LOGIN_ACCOUNT_LIMIT', 2)
    for _ in range(2):
        assert client.post('/api/password-reset', json={'email': 'alice@church.org'}).status_code == 200
    assert client.post('/api/password-reset', json={'email': 'alice@church.org'}).status_code == 429


def test_admin_resets_member_password(client):
    admin = auth(client, 'admin')
    alice = auth(client, 'alice')
    path = '/api/members/2/password'
    assert client.post(path, json={'password': 'temporary-pass-42'}, headers=alice).status_code == 403
    assert client.post('/api/members/1/password', json={'password': 'temporary-pass-42'}, headers=admin).status_code == 404
    assert client.post(path, json={'password': 'aaaaaaaaaaaaaaaa'}, headers=admin).status_code == 422
    assert client.post(path, json={'password': 'temporary-pass-42'}, headers=admin).status_code == 200
    assert client.get('/api/me', headers=alice).status_code == 401
    result = login(client, 'alice@church.org', 'temporary-pass-42')
    assert result.json()['user']['must_change_password'] is True
    with sys.modules['app'].db() as con:
        assert con.execute("SELECT count(*) FROM management_audit WHERE action='reset_password' AND member_id=2").fetchone()[0] == 1
