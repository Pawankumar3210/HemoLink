"""In-app notifications stored in MySQL."""

from flask import url_for
from sqlalchemy import func, select, update

from app.extensions import db
from app.models import Notification


def notify(user_id, title, message, related_type=None, related_id=None):
    """Queue a notification in the current transaction (caller commits)."""
    notification = Notification(
        user_id=user_id,
        title=title[:150],
        message=message[:500],
        related_type=related_type,
        related_id=related_id,
    )
    db.session.add(notification)
    return notification


def unread_count(user_id):
    stmt = (
        select(func.count())
        .select_from(Notification)
        .where(Notification.user_id == user_id, Notification.is_read.is_(False))
    )
    return db.session.scalar(stmt) or 0


def list_notifications(user_id, page, per_page=15):
    stmt = (
        select(Notification)
        .where(Notification.user_id == user_id)
        .order_by(Notification.created_at.desc(), Notification.id.desc())
    )
    return db.paginate(stmt, page=page, per_page=per_page, error_out=False)


def recent_notifications(user_id, limit=4):
    stmt = (
        select(Notification)
        .where(Notification.user_id == user_id)
        .order_by(Notification.created_at.desc(), Notification.id.desc())
        .limit(limit)
    )
    return list(db.session.scalars(stmt))


def mark_read(user_id, notification_id):
    """Mark one notification as read. Returns True if it belonged to the user."""
    result = db.session.execute(
        update(Notification)
        .where(Notification.id == notification_id, Notification.user_id == user_id)
        .values(is_read=True)
    )
    db.session.commit()
    return result.rowcount == 1


def mark_all_read(user_id):
    db.session.execute(
        update(Notification)
        .where(Notification.user_id == user_id, Notification.is_read.is_(False))
        .values(is_read=True)
    )
    db.session.commit()


def destination_url(notification):
    """Where a notification should lead the user (request context required)."""
    kind, target = notification.related_type, notification.related_id
    if kind == "contact_request" and target:
        return url_for("contact.detail", contact_id=target)
    if kind == "blood_request" and target:
        return url_for("blood_requests.detail", request_id=target)
    return url_for("dashboard.home")
