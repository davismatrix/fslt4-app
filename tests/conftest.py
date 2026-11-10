import pytest


@pytest.fixture(autouse=True)
def isolate_external_services(monkeypatch):
    # app.py loads the developer's .env without overriding existing variables, so
    # blanking SMTP_HOST here keeps tests from sending real email. Tests that need
    # SMTP (test_notifications) set their own values and mock smtplib.
    monkeypatch.setenv('SMTP_HOST', '')
    # Tests must not call the Have I Been Pwned API; breach tests mock it explicitly.
    monkeypatch.setenv('PASSWORD_BREACH_CHECK', 'off')
