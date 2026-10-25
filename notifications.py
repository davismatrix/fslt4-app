"""SMTP welcome notifications. No passwords or tax documents are emailed."""
import os
import smtplib
import ssl
from email.message import EmailMessage
from urllib.parse import urlsplit


def send_welcome(name: str, email: str) -> str:
    """Return SMTP acceptance status; acceptance does not guarantee inbox delivery."""
    host = os.environ.get('SMTP_HOST', '')
    sender = os.environ.get('SMTP_FROM', '')
    portal_url = os.environ.get('PORTAL_URL', '')
    if not all((host, sender, portal_url)):
        return 'not_configured'
    try:
        url = urlsplit(portal_url)
        if url.scheme not in ('http', 'https') or not url.netloc:
            return 'failed'
        church = os.environ.get('CHURCH_NAME', 'Love Assembly')
        message = EmailMessage()
        message['Subject'] = f'Welcome to {church} member portal'
        message['From'] = sender
        message['To'] = email
        message.set_content(
            f'Hello {name},\n\n'
            f'Your {church} member account has been created. '
            'You can sign in to access your giving donation slips when they are available.\n\n'
            f'Member portal: {portal_url}\nSign-in email: {email}\n\n'
            'Please contact the church office for your initial password or help signing in. '
            'Your password is not included in this email.\n\n'
            f'Thank you,\n{church}\n'
        )
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
    except (OSError, smtplib.SMTPException, ValueError):
        # Do not expose SMTP responses or credentials to API clients.
        return 'failed'
