"""SMTP welcome notifications. No passwords or tax documents are emailed."""
import os
import smtplib
import ssl
from email.message import EmailMessage
from urllib.parse import urlsplit


def portal_url():
    """Return the configured portal URL, or '' when SMTP delivery is not configured."""
    url = os.environ.get('PORTAL_URL', '')
    if not all((os.environ.get('SMTP_HOST', ''), os.environ.get('SMTP_FROM', ''), url)):
        return ''
    return url


def send_welcome(name: str, email: str) -> str:
    """Return SMTP acceptance status; acceptance does not guarantee inbox delivery."""
    url = portal_url()
    if not url:
        return 'not_configured'
    church = os.environ.get('CHURCH_NAME', 'Love Assembly')
    return send(email, f'Welcome to {church} member portal',
        f'Hello {name},\n\n'
        f'Your {church} member account has been created. '
        'You can sign in to access your giving donation slips when they are available.\n\n'
        f'Member portal: {url}\nSign-in email: {email}\n\n'
        'Please contact the church office for your initial password or help signing in. '
        'Your password is not included in this email. You will be asked to choose your own '
        'password the first time you sign in. You can also use "Forgot password?" on the '
        'sign-in page to set one yourself.\n\n'
        f'Thank you,\n{church}\n')


def send_password_reset(name: str, email: str, token: str) -> str:
    """Email a single-use reset link. The token is in the URL fragment, so it is not sent to servers or in Referer headers."""
    url = portal_url()
    if not url:
        return 'not_configured'
    church = os.environ.get('CHURCH_NAME', 'Love Assembly')
    return send(email, f'Reset your {church} member portal password',
        f'Hello {name},\n\n'
        f'We received a request to reset the password for your {church} member portal account.\n\n'
        f'Choose a new password using this link within 30 minutes:\n{url.rstrip("/")}/#reset={token}\n\n'
        'The link works once. If you did not request this, you can ignore this email; '
        'your password will not change.\n\n'
        f'Thank you,\n{church}\n')


def send(email: str, subject: str, body: str) -> str:
    try:
        url = urlsplit(os.environ.get('PORTAL_URL', ''))
        if url.scheme not in ('http', 'https') or not url.netloc:
            return 'failed'
        message = EmailMessage()
        message['Subject'] = subject
        message['From'] = os.environ['SMTP_FROM']
        message['To'] = email
        message.set_content(body)
        host = os.environ['SMTP_HOST']
        security = os.environ.get('SMTP_SECURITY', 'starttls').lower()
        if security not in ('starttls', 'ssl'):
            return 'failed'
        port = int(os.environ.get('SMTP_PORT', '465' if security == 'ssl' else '587'))
        context = ssl.create_default_context()
        connection = smtplib.SMTP_SSL(host, port, timeout=10, context=context) if security == 'ssl' else smtplib.SMTP(host, port, timeout=10)
        with connection as smtp:
            if security == 'starttls':
                smtp.starttls(context=context)
            username = os.environ.get('SMTP_USERNAME', '')
            if username:
                smtp.login(username, os.environ.get('SMTP_PASSWORD', ''))
            refused = smtp.send_message(message)
            return 'failed' if refused else 'sent'
    except (OSError, smtplib.SMTPException, ValueError, KeyError):
        # Do not expose SMTP responses or credentials to API clients.
        return 'failed'
