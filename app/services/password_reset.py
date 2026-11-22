"""Password reset: time-limited, single-use tokens stored only as hashes."""

import logging
from datetime import timedelta

from flask import current_app, url_for
from sqlalchemy import delete, select, update

from app.constants import ACCOUNT_ACTIVE
from app.extensions import db
from app.models import PasswordResetToken, User
from app.services import audit
from app.services.errors import ServiceError
from app.services.mailer import MailNotConfigured, send_mail
from app.utils.security import generate_token, hash_token
from app.utils.time import utcnow

logger = logging.getLogger(__name__)


def _reset_link(token):
    path = url_for("auth.reset_password", token=token)
    base = (current_app.config.get("PUBLIC_BASE_URL") or "").rstrip("/")
    if base:
        return base + path
    return url_for("auth.reset_password", token=token, _external=True)


def request_reset(email):
    """Create a token and email it. Silent for unknown or inactive accounts."""
    user = db.session.scalar(select(User).where(User.email == email))
    if user is None or user.account_status != ACCOUNT_ACTIVE:
        return False
    now = utcnow()
    db.session.execute(
        update(PasswordResetToken)
        .where(
            PasswordResetToken.user_id == user.id, PasswordResetToken.used_at.is_(None)
        )
        .values(used_at=now)
    )
    token = generate_token()
    minutes = current_app.config["PASSWORD_RESET_MINUTES"]
    db.session.add(
        PasswordResetToken(
            user_id=user.id,
            token_hash=hash_token(token),
            expires_at=now + timedelta(minutes=minutes),
        )
    )
    db.session.commit()
    body = (
        "Hello %s,\n\nUse the link below to choose a new HemoLink password. "
        "It works once and expires in %d minutes.\n\n%s\n\n"
        "If you did not ask for this, you can ignore this email.\n"
        % (user.full_name, minutes, _reset_link(token))
    )
    try:
        send_mail(user.email, "Reset your HemoLink password", body)
    except MailNotConfigured:
        logger.error("password reset requested but email delivery is not configured")
        return False
    except OSError:
        logger.exception("password reset email could not be sent")
        return False
    return True


def get_valid_token(token):
    row = db.session.scalar(
        select(PasswordResetToken).where(
            PasswordResetToken.token_hash == hash_token(token or "")
        )
    )
    if row is None or not row.is_usable:
        return None
    return row


def reset_password(token, new_password):
    row = get_valid_token(token)
    if row is None:
        raise ServiceError("This reset link is invalid or has expired.")
    user = row.user
    if user.account_status != ACCOUNT_ACTIVE:
        raise ServiceError("This reset link is invalid or has expired.")
    user.set_password(new_password)
    now = utcnow()
    db.session.execute(
        update(PasswordResetToken)
        .where(
            PasswordResetToken.user_id == user.id, PasswordResetToken.used_at.is_(None)
        )
        .values(used_at=now)
    )
    audit.record("user.password_reset", "user", user.id, actor=user)
    db.session.commit()
    return user


def purge_expired():
    """Delete expired or used tokens. Returns the number of rows removed."""
    result = db.session.execute(
        delete(PasswordResetToken).where(
            (PasswordResetToken.expires_at < utcnow())
            | PasswordResetToken.used_at.is_not(None)
        )
    )
    db.session.commit()
    return result.rowcount
