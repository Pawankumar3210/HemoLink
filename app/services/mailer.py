"""Outgoing email. Real SMTP when configured; a development-only console fallback."""

import logging
import smtplib
import ssl
from email.message import EmailMessage

from flask import current_app

logger = logging.getLogger("hemolink.mail")
OUTBOX_LIMIT = 50


class MailNotConfigured(RuntimeError):
    """Raised when email must be sent but no delivery method is available."""


def smtp_configured():
    return bool(current_app.config.get("MAIL_SERVER"))


def delivery_available():
    """True if reset emails can actually reach a person, or dev console is allowed."""
    return smtp_configured() or bool(current_app.config.get("ALLOW_CONSOLE_MAIL"))


def get_outbox():
    """Messages captured by the development/test console backend."""
    return current_app.extensions.setdefault("mail_outbox", [])


def send_mail(to, subject, body):
    """Send a plain-text email. Returns the backend used: ``smtp`` or ``console``."""
    config = current_app.config
    if smtp_configured():
        message = EmailMessage()
        message["From"] = config["MAIL_FROM"]
        message["To"] = to
        message["Subject"] = subject
        message.set_content(body)
        server, port = config["MAIL_SERVER"], config["MAIL_PORT"]
        with smtplib.SMTP(server, port, timeout=10) as smtp:
            if config.get("MAIL_USE_TLS"):
                smtp.starttls(context=ssl.create_default_context())
            if config.get("MAIL_USERNAME"):
                smtp.login(config["MAIL_USERNAME"], config["MAIL_PASSWORD"])
            smtp.send_message(message)
        logger.info("email sent via smtp subject=%r", subject)
        return "smtp"
    if config.get("ALLOW_CONSOLE_MAIL"):
        outbox = get_outbox()
        outbox.append({"to": to, "subject": subject, "body": body})
        del outbox[:-OUTBOX_LIMIT]
        logger.warning(
            "DEVELOPMENT ONLY - email NOT delivered. to=%s subject=%r\n%s",
            to,
            subject,
            body,
        )
        return "console"
    raise MailNotConfigured("No MAIL_SERVER configured and console mail is disabled.")
