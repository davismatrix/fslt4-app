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


def invite(client, monkeypatch, email='jane@church.org'):
    sender = MagicMock(return_value='sent')
    monkeypatch.setattr(sys.modules['app'], 'send_invite', sender)
    result = client.post('/api/members', json={'name': 'Jane', 'email': email, 'password': ''}, headers=auth(client, 'admin'))
    assert result.status_code == 201 and result.json()['invited'] is True
    return result.json()['id'], sender


def test_invited_member_sets_own_password(client, monkeypatch):
    changed = MagicMock()
    monkeypatch.setattr(sys.modules['app'], 'send_password_changed', changed)
    member_id, sender = invite(client, monkeypatch)
    sender.assert_called_once()
    token = sender.call_args.args[2]
    members = client.get('/api/members', headers=auth(client, 'admin')).json()
    assert next(m for m in members if m['id'] == member_id)['invite_pending'] is True
    assert client.post('/api/password-reset/confirm', json={'token': token, 'password': NEW}).status_code == 200
    result = login(client, 'jane@church.org', NEW)
    assert result.status_code == 200
    assert not result.json()['user']['must_change_password'] and not result.json()['user']['invite_pending']
    # Accepting an invitation is not a "password changed" event.
    changed.assert_not_called()


def test_invite_expires_after_seven_days_and_can_be_resent(client, monkeypatch):
    module = sys.modules['app']
    member_id, sender = invite(client, monkeypatch)
    first = sender.call_args.args[2]
    with module.db() as con:
        expires = con.execute('SELECT expires FROM password_resets WHERE user_id=?', (member_id,)).fetchone()[0]
    import time
    assert 6.9 * 86400 < expires - time.time() <= 7 * 86400
    admin = auth(client, 'admin')
    assert client.post(f'/api/members/{member_id}/invite', headers=auth(client, 'alice')).status_code == 403
    assert client.post(f'/api/members/{member_id}/invite', headers=admin).json() == {'notification': 'sent'}
    assert client.post('/api/password-reset/confirm', json={'token': first, 'password': NEW}).status_code == 400
    assert client.post('/api/password-reset/confirm', json={'token': sender.call_args.args[2], 'password': NEW}).status_code == 200
    assert client.post(f'/api/members/{member_id}/invite', headers=admin).status_code == 409
    with module.db() as con:
        assert con.execute("SELECT count(*) FROM management_audit WHERE action='resend_invite'").fetchone()[0] == 1


def test_revoked_invite_cannot_be_resent(client, monkeypatch):
    member_id, _ = invite(client, monkeypatch)
    admin = auth(client, 'admin')
    client.post(f'/api/members/{member_id}/access', json={'active': False}, headers=admin)
    assert client.post(f'/api/members/{member_id}/invite', headers=admin).status_code == 409


def test_password_change_notifications(client, monkeypatch):
    module = sys.modules['app']
    changed = MagicMock()
    monkeypatch.setattr(module, 'send_password_changed', changed)
    monkeypatch.setattr(module, 'send_password_reset', MagicMock())
    alice = auth(client, 'alice')
    client.post('/api/password', json={'current_password': 'correct-horse-battery', 'new_password': NEW}, headers=alice)
    changed.assert_called_once_with('Alice', 'alice@church.org')
    client.post('/api/members/2/password', json={'password': 'temporary-pass-42'}, headers=auth(client, 'admin'))
    changed.assert_called_with('Alice', 'alice@church.org', True)
    client.post('/api/password-reset', json={'email': 'alice@church.org'})
    client.post('/api/password-reset/confirm', json={'token': module.send_password_reset.call_args.args[2], 'password': NEW + '!'})
    assert changed.call_count == 3


def pwned_response(body):
    response = MagicMock()
    response.__enter__.return_value.read.return_value = body.encode()
    return MagicMock(return_value=response)


def test_breached_passwords_are_rejected(client, monkeypatch):
    import hashlib
    module = sys.modules['app']
    monkeypatch.setenv('PASSWORD_BREACH_CHECK', 'on')
    suffix = hashlib.sha1(NEW.encode()).hexdigest().upper()[5:]
    urlopen = pwned_response(f'0000000000000000000000000000000000A:0\r\n{suffix}:42\r\n')
    monkeypatch.setattr(module.urllib.request, 'urlopen', urlopen)
    alice = auth(client, 'alice')
    result = client.post('/api/password', json={'current_password': 'correct-horse-battery', 'new_password': NEW}, headers=alice)
    assert result.status_code == 422 and 'breach' in result.json()['detail']
    request = urlopen.call_args.args[0]
    # Only the 5-character prefix leaves the server.
    assert request.full_url.endswith('/range/' + hashlib.sha1(NEW.encode()).hexdigest().upper()[:5])
    assert request.get_header('Add-padding') == 'true'


def test_breach_check_ignores_padding_and_fails_open(client, monkeypatch):
    import hashlib
    module = sys.modules['app']
    monkeypatch.setenv('PASSWORD_BREACH_CHECK', 'on')
    suffix = hashlib.sha1(NEW.encode()).hexdigest().upper()[5:]
    monkeypatch.setattr(module.urllib.request, 'urlopen', pwned_response(f'{suffix}:0\r\n'))
    assert module.password_problem(NEW) is None
    monkeypatch.setattr(module.urllib.request, 'urlopen', MagicMock(side_effect=OSError('offline')))
    assert module.password_problem(NEW) is None


def test_successful_sign_in_clears_own_attempts(client, monkeypatch):
    monkeypatch.setattr(sys.modules['app'], 'LOGIN_ACCOUNT_LIMIT', 2)
    for _ in range(5):
        assert login(client, 'alice@church.org', 'wrong').status_code == 401
        assert login(client, 'alice@church.org', 'correct-horse-battery').status_code == 200


def test_account_lockout_is_per_client_with_global_cap(client, monkeypatch):
    module = sys.modules['app']
    monkeypatch.setattr(module, 'LOGIN_ACCOUNT_LIMIT', 2)
    monkeypatch.setattr(module, 'LOGIN_ACCOUNT_GLOBAL_LIMIT', 4)
    monkeypatch.setattr(module, 'TRUSTED_PROXIES', {'testclient'})
    attacker = {'X-Forwarded-For': '203.0.113.9'}
    for _ in range(2):
        assert client.post('/api/login', json={'email': 'alice@church.org', 'password': 'wrong'}, headers=attacker).status_code == 401
    assert client.post('/api/login', json={'email': 'alice@church.org', 'password': 'wrong'}, headers=attacker).status_code == 429
    # The member, on a different network, can still sign in.
    assert client.post('/api/login', json={'email': 'alice@church.org', 'password': 'correct-horse-battery'}, headers={'X-Forwarded-For': '198.51.100.7'}).status_code == 200
    for address in ('192.0.2.1', '192.0.2.2'):
        client.post('/api/login', json={'email': 'alice@church.org', 'password': 'wrong'}, headers={'X-Forwarded-For': address})
    assert client.post('/api/login', json={'email': 'alice@church.org', 'password': 'wrong'}, headers={'X-Forwarded-For': '192.0.2.3'}).status_code == 429


def test_trusted_proxy_uses_nearest_untrusted_hop(client, monkeypatch):
    module = sys.modules['app']
    monkeypatch.setattr(module, 'LOGIN_CLIENT_LIMIT', 2)
    monkeypatch.setattr(module, 'TRUSTED_PROXIES', {'testclient', '10.0.0.2'})
    for i in range(2):
        # A client-supplied leftmost hop cannot change the identified address.
        headers = {'X-Forwarded-For': f'198.51.100.{i}, 203.0.113.5, 10.0.0.2'}
        assert client.post('/api/login', json={'email': f'u{i}@church.org', 'password': 'wrong'}, headers=headers).status_code == 401
    assert client.post('/api/login', json={'email': 'x@church.org', 'password': 'wrong'}, headers={'X-Forwarded-For': '203.0.113.5'}).status_code == 429
    assert client.post('/api/login', json={'email': 'x@church.org', 'password': 'wrong'}, headers={'X-Forwarded-For': '203.0.113.6'}).status_code == 401
