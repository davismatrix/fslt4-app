import smtplib
from unittest.mock import MagicMock

import pytest
import notifications


@pytest.fixture
def smtp(monkeypatch):
    for key, value in {'SMTP_HOST':'smtp.example.com','SMTP_FROM':'office@example.com','PORTAL_URL':'https://members.example.com','SMTP_USERNAME':'mailer','SMTP_PASSWORD':'smtp-secret','SMTP_SECURITY':'starttls','SMTP_PORT':'587'}.items():
        monkeypatch.setenv(key, value)
    factory = MagicMock()
    factory.return_value.__enter__.return_value.send_message.return_value = {}
    monkeypatch.setattr(notifications.smtplib, 'SMTP', factory)
    return factory


def test_welcome_message(smtp):
    assert notifications.send_welcome('Jane', 'jane@example.com') == 'sent'
    connection = smtp.return_value.__enter__.return_value
    connection.starttls.assert_called_once()
    connection.login.assert_called_once_with('mailer', 'smtp-secret')
    message = connection.send_message.call_args.args[0]
    assert message['To'] == 'jane@example.com'
    assert 'https://members.example.com' in message.get_content()
    assert 'smtp-secret' not in message.as_string()


def test_missing_config(monkeypatch, smtp):
    monkeypatch.delenv('SMTP_HOST')
    assert notifications.send_welcome('Jane', 'jane@example.com') == 'not_configured'
    smtp.assert_not_called()


def test_failure(smtp):
    smtp.side_effect = smtplib.SMTPException('private provider failure')
    assert notifications.send_welcome('Jane', 'jane@example.com') == 'failed'


def test_ssl(monkeypatch, smtp):
    monkeypatch.setenv('SMTP_SECURITY', 'ssl')
    ssl_factory = MagicMock()
    ssl_factory.return_value.__enter__.return_value.send_message.return_value = {}
    monkeypatch.setattr(notifications.smtplib, 'SMTP_SSL', ssl_factory)
    assert notifications.send_welcome('Jane', 'jane@example.com') == 'sent'
    smtp.assert_not_called()
    ssl_factory.return_value.__enter__.return_value.starttls.assert_not_called()


def test_password_reset_message(smtp):
    assert notifications.send_password_reset('Jane', 'jane@example.com', 'secret-token') == 'sent'
    message = smtp.return_value.__enter__.return_value.send_message.call_args.args[0]
    assert 'https://members.example.com/password#reset=secret-token' in message.get_content()


def test_password_reset_not_configured(monkeypatch, smtp):
    monkeypatch.delenv('SMTP_HOST')
    assert notifications.send_password_reset('Jane', 'jane@example.com', 'secret-token') == 'not_configured'


def test_invite_message(smtp):
    assert notifications.send_invite('Jane', 'jane@example.com', 'invite-token') == 'sent'
    message = smtp.return_value.__enter__.return_value.send_message.call_args.args[0]
    assert 'https://members.example.com/password#invite=invite-token' in message.get_content()
    assert '7 days' in message.get_content()


@pytest.mark.parametrize('by_office, phrase', [(False, 'was just changed'), (True, 'temporary password')])
def test_password_changed_message(smtp, by_office, phrase):
    assert notifications.send_password_changed('Jane', 'jane@example.com', by_office) == 'sent'
    message = smtp.return_value.__enter__.return_value.send_message.call_args.args[0]
    assert phrase in message.get_content() and 'contact the church office' in message.get_content()
