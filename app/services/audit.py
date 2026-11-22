"""Audit logging. Never put credentials, tokens or contact details in ``details``."""

from flask_login import current_user

from app.extensions import db
from app.models import AuditLog


def record(action, entity_type=None, entity_id=None, details=None, actor=None):
    """Queue an audit entry in the current transaction (caller commits)."""
    if actor is None and current_user and current_user.is_authenticated:
        actor = current_user
    entry = AuditLog(
        actor_id=getattr(actor, "id", None),
        action=action[:60],
        entity_type=entity_type,
        entity_id=entity_id,
        details=(details or "")[:500] or None,
    )
    db.session.add(entry)
    return entry
